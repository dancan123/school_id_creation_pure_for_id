import os
import uuid
import datetime
from pathlib import Path
from config import Config
from extensions import db
from models import School, Student, CardRecord, GenerationJob, QRVerificationToken
from services.card_renderer import CardRenderer
from services.qr_service import QRService

class BulkGenerator:
    @staticmethod
    def run_generation(job_id, school_id, student_ids=None, print_format="cr80_single", base_url="http://localhost:5000"):
        """Executes batched card generation for student_ids.
           Updates job progress in database and outputs print-ready PDF.
        """
        job = db.session.get(GenerationJob, job_id)
        if not job:
            return None

        school = db.session.get(School, school_id)
        if not school:
            job.status = "failed"
            db.session.commit()
            return None

        job.status = "processing"
        db.session.commit()

        # Query students
        query = Student.query.filter_by(school_id=school_id, is_archived=False)
        if student_ids:
            query = query.filter(Student.id.in_(student_ids))
        
        students = query.order_by(Student.class_name, Student.stream_name, Student.admission_number).all()
        job.total_count = len(students)
        db.session.commit()

        card_image_pairs = []
        success_count = 0
        failed_count = 0

        # Expiry date
        exp_year = int(school.academic_year) + (school.validity_years or 4)
        expiry_date = datetime.date(exp_year, 12, 31)
        issue_date = datetime.date.today()

        for idx, student in enumerate(students, start=1):
            try:
                # Check if student already has an active card record
                card = CardRecord.query.filter_by(student_id=student.id, status="active").first()
                if not card:
                    card_number = f"{school.card_prefix or 'ID-'}{student.admission_number}"
                    token_str = secrets_token = QRService.generate_unique_token()
                    
                    card = CardRecord(
                        school_id=school.id,
                        student_id=student.id,
                        template_id=school.default_template_id,
                        card_number=card_number,
                        qr_token=token_str,
                        issue_date=issue_date,
                        expiry_date=expiry_date,
                        status="active",
                        print_status="pending",
                        print_count=0,
                        generation_batch_id=job_id
                    )
                    db.session.add(card)
                    db.session.flush()

                    # Add verification token entry
                    v_token = QRVerificationToken(
                        token=token_str,
                        school_id=school.id,
                        student_id=student.id,
                        card_record_id=card.id,
                        is_valid=True
                    )
                    db.session.add(v_token)
                else:
                    card.generation_batch_id = job_id

                # Render front & back images
                f_path, b_path = CardRenderer.save_card_images(school, student, card, base_url)
                card_image_pairs.append((f_path, b_path))

                # Update student
                student.card_status = "active"
                student.card_number = card.card_number
                student.issue_date = issue_date
                student.expiry_date = expiry_date

                success_count += 1
            except Exception as e:
                failed_count += 1
                print(f"Error generating card for student {student.admission_number}: {e}")

            # Update progress every 20 records or on complete
            if idx % 20 == 0 or idx == len(students):
                job.processed_count = idx
                job.success_count = success_count
                job.failed_count = failed_count
                db.session.commit()

        # Generate Compiled Print-Ready PDF
        pdf_filename = f"batch_{school.id}_{job_id[:8]}_{print_format}.pdf"
        output_pdf_path = Config.PDFS_DIR / pdf_filename

        try:
            if print_format == "cr80_single":
                # For CR80 single: we compile all cards sequentially into one multipage CR80 PDF
                # (Page 1: Front 1, Page 2: Back 1, Page 3: Front 2, Page 4: Back 2...)
                from reportlab.pdfgen import canvas
                from reportlab.lib.units import mm
                w_pt = 85.60 * mm
                h_pt = 53.98 * mm
                c = canvas.Canvas(str(output_pdf_path), pagesize=(w_pt, h_pt))
                for f_img, b_img in card_image_pairs:
                    c.drawImage(str(f_img), 0, 0, width=w_pt, height=h_pt)
                    c.showPage()
                    c.drawImage(str(b_img), 0, 0, width=w_pt, height=h_pt)
                    c.showPage()
                c.save()
            else:
                # A4 sheets: 8 per page or 10 per page
                layout = "8_per_page" if "8" in print_format else "10_per_page"
                CardRenderer.generate_a4_sheet_pdf(card_image_pairs, output_pdf_path, layout=layout)

            job.pdf_filename = pdf_filename
            job.status = "completed"
        except Exception as e:
            job.status = "failed"
            print(f"Failed to generate PDF for batch {job_id}: {e}")

        job.completed_at = datetime.datetime.utcnow()
        db.session.commit()

        return job
