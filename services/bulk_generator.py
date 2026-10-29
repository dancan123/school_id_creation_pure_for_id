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

        # Generate High-Resolution 300 DPI Cards ZIP Archive for direct card printers
        try:
            import zipfile
            zip_filename = f"batch_{school.id}_{job_id[:8]}_cards_300dpi.zip"
            output_zip_path = Config.PDFS_DIR / zip_filename
            with zipfile.ZipFile(str(output_zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
                for f_img, b_img in card_image_pairs:
                    if os.path.exists(f_img):
                        zf.write(str(f_img), arcname=f"cards/{os.path.basename(f_img)}")
                    if os.path.exists(b_img):
                        zf.write(str(b_img), arcname=f"cards/{os.path.basename(b_img)}")
                meta_txt = (
                    f"BATCH ID CARD GENERATION REPORT\n"
                    f"=================================\n"
                    f"School / Organization: {school.name}\n"
                    f"Batch ID: {job_id}\n"
                    f"Print Format: {print_format}\n"
                    f"Generated At: {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                    f"Total Students Processed: {len(students)}\n"
                    f"Successfully Generated: {success_count}\n"
                    f"Failed: {failed_count}\n\n"
                    f"Image Specifications:\n"
                    f"- Format: High-Definition PNG (300 DPI)\n"
                    f"- Dimension: 1011 x 638 px (85.60 x 53.98 mm Standard CR80 PVC Card)\n"
                    f"- Ready for direct feed into Zebra, Evolis, Fargo, Magicard, Datacard printers.\n"
                )
                zf.writestr("BATCH_INFO.txt", meta_txt)
        except Exception as ze:
            print(f"Warning: Failed to generate cards ZIP for batch {job_id}: {ze}")

        job.completed_at = datetime.datetime.utcnow()
        db.session.commit()

        return job

    @staticmethod
    def ensure_batch_zip(job_id):
        """Ensures that a 300 DPI PNG cards ZIP exists for the given job_id. If missing, builds it dynamically."""
        job = db.session.get(GenerationJob, job_id)
        if not job:
            return None
        school = db.session.get(School, job.school_id)
        zip_filename = f"batch_{school.id}_{job_id[:8]}_cards_300dpi.zip"
        output_zip_path = Config.PDFS_DIR / zip_filename
        if output_zip_path.exists():
            return output_zip_path

        # Dynamically build zip from associated cards
        import zipfile
        cards = CardRecord.query.filter_by(generation_batch_id=job_id).all()
        if not cards:
            cards = CardRecord.query.filter_by(school_id=school.id).all()

        with zipfile.ZipFile(str(output_zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
            added = 0
            for c in cards:
                if c.front_image_filename:
                    f_p = Config.GENERATED_CARDS_DIR / c.front_image_filename
                    if f_p.exists():
                        zf.write(str(f_p), arcname=f"cards/{c.front_image_filename}")
                        added += 1
                if c.back_image_filename:
                    b_p = Config.GENERATED_CARDS_DIR / c.back_image_filename
                    if b_p.exists():
                        zf.write(str(b_p), arcname=f"cards/{c.back_image_filename}")
                        added += 1
            meta_txt = (
                f"BATCH ID CARD GENERATION REPORT (Archive)\n"
                f"=========================================\n"
                f"School / Organization: {school.name}\n"
                f"Batch ID: {job_id}\n"
                f"Total Image Files: {added}\n"
                f"Resolution: 300 DPI Standard CR80 PVC Ready\n"
            )
            zf.writestr("BATCH_INFO.txt", meta_txt)

        return output_zip_path
