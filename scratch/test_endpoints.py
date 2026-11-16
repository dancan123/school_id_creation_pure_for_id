import sys, os
sys.path.insert(0, os.path.abspath("."))
import traceback
from app import app
from models import User, School, Student, CardRecord, GenerationJob

with app.app_context():
    client = app.test_client()
    user = User.query.first()
    school = School.query.first()
    student = Student.query.first()
    card = CardRecord.query.filter_by(student_id=student.id).first()

    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True
        sess['active_school_id'] = school.id

    endpoints = [
        ("GET", "/single-id/"),
        ("GET", f"/single-id/?student_id={student.id}"),
        ("GET", f"/single-id/preview/front/{student.id}"),
        ("GET", f"/single-id/preview/back/{student.id}"),
        ("GET", f"/single-id/history/{student.id}"),
        ("GET", "/bulk-generate/"),
        ("GET", f"/single-id/download/{card.id}" if card else None),
        ("POST", "/single-id/generate", {"student_id": str(student.id)}),
        ("POST", "/bulk-generate/start", {
            "scope": "all",
            "card_status_filter": "all",
            "photo_filter": "all",
            "print_format": "cr80_single"
        }),
        ("POST", "/bulk-generate/start", {
            "scope": "all",
            "card_status_filter": "all",
            "photo_filter": "all",
            "print_format": "a4_grid_8"
        }),
        ("POST", "/bulk-generate/start", {
            "scope": "all",
            "card_status_filter": "all",
            "photo_filter": "all",
            "print_format": "a4_grid_10"
        }),
        ("POST", "/single-id/renew-bulk", {
            "scope": "all",
            "renewal_notes": "Bulk test"
        }),
        ("GET", "/students/"),
        ("GET", f"/students/{student.id}/edit"),
        ("GET", "/schools/settings"),
    ]

    print("=== TESTING ENDPOINTS ===")
    for item in endpoints:
        if not item or not item[1]:
            continue
        method = item[0]
        url = item[1]
        data = item[2] if len(item) > 2 else None
        
        try:
            if method == "GET":
                resp = client.get(url, follow_redirects=False)
            else:
                resp = client.post(url, data=data, follow_redirects=False)
            
            status = resp.status_code
            if status >= 500:
                print(f"[FAIL 500] {method} {url} -> {status}")
                print(resp.data.decode("utf-8", errors="ignore")[:300])
            elif status >= 400:
                print(f"[WARN {status}] {method} {url}")
            else:
                print(f"[OK {status}] {method} {url}")
        except Exception as e:
            print(f"[EXCEPTION] {method} {url} -> {e}")
            traceback.print_exc()
