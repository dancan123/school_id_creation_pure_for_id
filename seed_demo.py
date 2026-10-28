import datetime
import secrets
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from app import create_app
from config import Config
from extensions import db
from models import School, Student, CardRecord, QRVerificationToken, User
from services.card_renderer import CardRenderer
from services.qr_service import QRService

def create_sample_avatar(path, name_initials="DM", bg_color=(30, 58, 138)):
    """Generates a clean student portrait avatar image."""
    img = Image.new("RGB", (300, 380), color=(241, 245, 249))
    draw = ImageDraw.Draw(img)
    
    # Outer background gradient or fill
    draw.rectangle([0, 0, 300, 380], fill=(226, 232, 240))
    
    # Head & Shoulders silhouette
    # Head circle
    draw.ellipse([85, 60, 215, 190], fill=bg_color)
    # Body/Shoulders
    draw.chord([40, 180, 260, 420], 180, 360, fill=bg_color)

    # Initials badge on chest
    draw.ellipse([110, 240, 190, 320], fill=(245, 158, 11))
    try:
        font = ImageFont.truetype("arialbd.ttf", 36)
    except Exception:
        font = ImageFont.load_default()
    draw.text((122, 260), name_initials, fill=(15, 23, 42), font=font)

    img.save(path, "JPEG", quality=95)
    return path

def create_sample_school_logo(path, initials="AHS", pri_color=(30, 58, 138), sec_color=(245, 158, 11)):
    """Generates a circular school crest emblem."""
    img = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Shield / Circle Outer
    draw.ellipse([10, 10, 190, 190], fill=pri_color, outline=sec_color, width=6)
    draw.ellipse([25, 25, 175, 175], fill=(255, 255, 255), outline=pri_color, width=2)
    
    # Inner emblem circle
    draw.ellipse([45, 45, 155, 155], fill=sec_color)

    try:
        font = ImageFont.truetype("arialbd.ttf", 36)
    except Exception:
        font = ImageFont.load_default()

    draw.text((62, 75), initials, fill=pri_color, font=font)
    img.save(path, "PNG")
    return path

def seed_demo_data():
    app = create_app()
    with app.app_context():
        print("Seeding demo data into SQLite database...")
        db.create_all()

        # 1. School: Alliance High School
        school = School.query.filter_by(name="Alliance High School").first()
        if not school:
            school = School(
                name="Alliance High School",
                code="AHS-001",
                motto="Strong to Serve",
                po_box="P.O. Box 7 - 00902",
                town="Kikuyu",
                county="Kiambu",
                phone="+254 722 000111",
                email="info@alliancehigh.ac.ke",
                website="https://alliancehigh.ac.ke",
                primary_color="#1E3A8A",   # Royal Navy Blue
                secondary_color="#F59E0B", # Gold
                accent_color="#10B981",    # Emerald
                card_bg_color="#FFFFFF",
                text_color="#0F172A",
                principal_name="Chief Principal",
                academic_year="2026",
                card_prefix="AHS-",
                validity_years=4
            )
            db.session.add(school)
            db.session.commit()

        # Generate school logo if missing
        logo_fn = "alliance_logo.png"
        logo_path = Config.LOGOS_DIR / logo_fn
        if not logo_path.exists():
            create_sample_school_logo(logo_path, initials="AHS")
        school.logo_filename = logo_fn
        db.session.commit()

        # 2. Add Second Demo School: Lenana School for Multi-School testing
        lenana = School.query.filter_by(name="Lenana School").first()
        if not lenana:
            lenana = School(
                name="Lenana School",
                code="LNN-001",
                motto="Nihil Praeter Optimum",
                po_box="P.O. Box 30175 - 00100",
                town="Nairobi",
                county="Nairobi",
                phone="+254 720 000222",
                email="info@lenana.ac.ke",
                website="https://lenana.ac.ke",
                primary_color="#065F46",   # Forest Green
                secondary_color="#D97706", # Amber
                accent_color="#FBBF24",
                card_bg_color="#FFFFFF",
                text_color="#0F172A",
                principal_name="Principal",
                academic_year="2026",
                card_prefix="LNN-",
                validity_years=4
            )
            db.session.add(lenana)
            db.session.commit()

            lenana_logo_fn = "lenana_logo.png"
            create_sample_school_logo(Config.LOGOS_DIR / lenana_logo_fn, initials="LS", pri_color=(6, 95, 70), sec_color=(217, 119, 6))
            lenana.logo_filename = lenana_logo_fn
            db.session.commit()

        # 3. Create Demo Student 00100
        student_00100 = Student.query.filter_by(school_id=school.id, admission_number="00100").first()
        photo_00100_fn = "photo_00100.jpg"
        photo_00100_path = Config.PHOTOS_DIR / photo_00100_fn
        if not photo_00100_path.exists():
            create_sample_avatar(photo_00100_path, name_initials="DK", bg_color=(30, 58, 138))

        if not student_00100:
            student_00100 = Student(
                school_id=school.id,
                admission_number="00100",
                full_name="David Kimani Mwangi",
                class_name="Form 3",
                stream_name="East",
                gender="Male",
                dob="2009-05-14",
                academic_year="2026",
                parent_name="James Mwangi",
                parent_phone="0722123456",
                blood_group="O+",
                house_or_dorm="Simba",
                photo_filename=photo_00100_fn,
                card_status="active"
            )
            db.session.add(student_00100)
            db.session.commit()
            print("Created Demo Student: Admission No 00100 (David Kimani Mwangi)")
        else:
            student_00100.photo_filename = photo_00100_fn
            student_00100.card_status = "active"
            db.session.commit()

        # Generate & Pre-render ID Card for 00100
        card_00100 = CardRecord.query.filter_by(student_id=student_00100.id).first()
        if not card_00100:
            token_00100 = QRService.generate_unique_token()
            card_00100 = CardRecord(
                school_id=school.id,
                student_id=student_00100.id,
                card_number=f"{school.card_prefix}00100",
                qr_token=token_00100,
                issue_date=datetime.date.today(),
                expiry_date=datetime.date(2029, 12, 31),
                status="active",
                print_status="pending",
                print_count=0
            )
            db.session.add(card_00100)
            db.session.flush()

            v_token = QRVerificationToken(
                token=token_00100,
                school_id=school.id,
                student_id=student_00100.id,
                card_record_id=card_00100.id,
                is_valid=True
            )
            db.session.add(v_token)
            db.session.commit()

        # Render Front, Back, and Single PDF
        f_p, b_p = CardRenderer.save_card_images(school, student_00100, card_00100)
        pdf_fn = f"card_{school.id}_{student_00100.admission_number}_{card_00100.qr_token[:6]}.pdf"
        pdf_path = Config.PDFS_DIR / pdf_fn
        CardRenderer.generate_single_cr80_pdf(f_p, b_p, pdf_path)
        card_00100.single_pdf_filename = pdf_fn
        student_00100.card_number = card_00100.card_number
        student_00100.issue_date = card_00100.issue_date
        student_00100.expiry_date = card_00100.expiry_date
        db.session.commit()

        print(f"Pre-rendered front/back cards and CR80 print PDF for student 00100: {pdf_fn}")

        # 4. Add additional cohort of demo students across classes for rich tasting
        demo_cohort = [
            ("00101", "Faith Wanjiku Kariuki", "Form 1", "North", "Female", "2011-02-18", "0723456781", "A+", "Chui"),
            ("00102", "Emmanuel Kipchirchir", "Form 1", "South", "Male", "2011-08-22", "0723456782", "B+", "Kifaru"),
            ("00103", "Mercy Chebet Langat", "Form 2", "East", "Female", "2010-03-12", "0723456783", "O+", "Twiga"),
            ("00104", "Brian Otieno Onyango", "Form 2", "West", "Male", "2010-11-04", "0723456784", "AB+", "Simba"),
            ("00105", "Grace Muthoni Njeri", "Form 3", "North", "Female", "2009-07-19", "0723456785", "A-", "Nyati"),
            ("00106", "Kevin Mutua Musyoka", "Form 4", "East", "Male", "2008-01-30", "0723456786", "O+", "Chui"),
            ("00107", "Amina Hassan Ali", "Form 4", "West", "Female", "2008-09-15", "", "B-", "Kifaru")
        ]

        for adm, name, cls, strm, gnd, dob, phone, bg, house in demo_cohort:
            if not Student.query.filter_by(school_id=school.id, admission_number=adm).first():
                ph_fn = f"photo_{adm}.jpg"
                create_sample_avatar(Config.PHOTOS_DIR / ph_fn, name_initials="".join([p[0] for p in name.split()[:2]]))
                std = Student(
                    school_id=school.id,
                    admission_number=adm,
                    full_name=name,
                    class_name=cls,
                    stream_name=strm,
                    gender=gnd,
                    dob=dob,
                    academic_year="2026",
                    parent_name=f"Parent of {name.split()[0]}",
                    parent_phone=phone,
                    blood_group=bg,
                    house_or_dorm=house,
                    photo_filename=ph_fn,
                    card_status="pending"
                )
                db.session.add(std)

        db.session.commit()
        print(f"Demo seeding complete! Total students in {school.name}: {Student.query.filter_by(school_id=school.id).count()}")

if __name__ == "__main__":
    seed_demo_data()
