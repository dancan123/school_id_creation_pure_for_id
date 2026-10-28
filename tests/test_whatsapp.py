import pytest
from utils import (
    clean_kenyan_phone_for_whatsapp,
    build_whatsapp_link,
    get_whatsapp_onboarding_share_url,
    get_whatsapp_parent_card_notice_url
)
from models import School, Student, CardRecord

def test_clean_kenyan_phone():
    assert clean_kenyan_phone_for_whatsapp("0722123456") == "254722123456"
    assert clean_kenyan_phone_for_whatsapp("0112123456") == "254112123456"
    assert clean_kenyan_phone_for_whatsapp("+254 722-123-456") == "254722123456"
    assert clean_kenyan_phone_for_whatsapp("254722123456") == "254722123456"
    assert clean_kenyan_phone_for_whatsapp(None) is None
    assert clean_kenyan_phone_for_whatsapp("") is None

def test_build_whatsapp_link():
    link_with_phone = build_whatsapp_link("0722123456", "Hello Parent")
    assert link_with_phone.startswith("https://wa.me/254722123456?text=Hello")
    
    broadcast_link = build_whatsapp_link(phone=None, message="School ID Announcement")
    assert broadcast_link.startswith("https://wa.me/?text=School")

def test_get_whatsapp_onboarding_share_url():
    school = School(name="Lenana School", code="LEN-001", academic_year="2026")
    url = get_whatsapp_onboarding_share_url(school, "http://localhost:5000/onboard/LEN-001")
    assert "https://wa.me/?text=" in url
    assert "Lenana" in url or "LEN-001" in url

def test_get_whatsapp_parent_card_notice_url():
    school = School(name="Kenya High", academic_year="2026")
    student = Student(full_name="Jane Doe", admission_number="3001", class_name="Grade 7", parent_phone="0711999888")
    card = CardRecord(card_number="KH-2026-001")
    
    url = get_whatsapp_parent_card_notice_url(student, school, card)
    assert url.startswith("https://wa.me/254711999888?text=")
    assert "Jane" in url
