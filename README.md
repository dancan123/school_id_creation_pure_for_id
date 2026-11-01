# EduID Kenya - School ID Card Generation System

A complete, production-ready, standalone **School ID Card Generation System** built for Kenyan primary, junior secondary (JSS), senior secondary schools, and colleges.

The system is designed for **single-computer or centralized operations** using persistent SQLite database storage with multi-school isolation, customizable institutional color schemes, photo matching, live card design studios, individual card production, and high-performance bulk generation.

---

## 🌟 Key Features

### 1. Multi-School at a Go with Isolated Settings
- Manage several schools on a single machine or server without data crossover.
- 1-click **Active School Switcher** in the top navigation bar.
- Individual school customization:
  - School Name, Motto, Postal Address, Town, County, Phone, Email, Website.
  - Custom Color Palette: Primary Branding Color, Secondary Accent, Tertiary Accent, and Text Color.
  - School Crest / Logo upload.
  - Principal Signature upload and signatory name/title.
  - Card rules: Academic Year, Card Prefix (e.g. `ID-` or `AHS-`), Validity period in years (default 4 years).
  - Back-of-card terms, disclaimers, and emergency telephone hotlines.

### 2. Individual ID Generation Workflow
- Search or select a student from the register (or click to add one).
- Live interactive front and back card preview reflecting the school's colors, logo, and student photo.
- Instant 1-click generation of print-ready single CR80 PDF (85.60 × 53.98 mm).
- Replacement and reprint workflow with audit reason tracking without creating duplicate student records.

### 3. Bulk Import Wizard (Excel / CSV + Photos ZIP)
- Download standard Kenyan student spreadsheet template with one click.
- Automatic column mapping with regex recognition for common Kenyan spreadsheet variations (`Admission No`, `Full Name`, `Form/Class`, `Stream`, `DOB`, `Gender`, `Parent Phone`, `Blood Group`, `House/Dorm`).
- Automatic photograph matching from uploaded ZIP archives matching admission numbers (`1001.jpg`, `ADM-1002.png`, etc.).
- Robust pre-validation detecting missing fields, duplicates in file or database, and missing photos.
- Downloadable validation error report in CSV format with exact row numbers and actionable descriptions.
- Transactional database commit of validated records.

### 4. Bulk ID Generation Engine
- Select scope: Entire school, specific class, or specific stream.
- Choose print output format:
  - **CR80 PVC Card Printer Format**: Multipage PDF (85.60 × 53.98 mm) with alternating front and back pages for direct PVC badge printers (Fargo, Zebra, Evolis, Magicard).
  - **A4 Sheet Proofing / Outsourcing Layout**: Standard A4 paper with an 8-card grid (2×4) or 10-card grid (2×5) with mirrored duplex reverse alignment for two-sided paper printing.
- Resumable batch execution with progress counters and batch history logs.

### 5. ID Card Design Studio & Presets
- 5 Kenyan national and county school color theme presets:
  1. *Classic Royal* (Navy Blue & Gold)
  2. *Emerald Crest* (Forest Green & Amber)
  3. *Maroon Elite* (Crimson Maroon & Gold)
  4. *Modern Academy* (Deep Slate & Cyan)
  5. *Highland Majesty* (Royal Purple & Gold)
- 1-click preset application to current school branding with live preview.

### 6. Cryptographic QR Verification
- Each card generates a unique, non-sequential 32-character hexadecimal token.
- Secure public verification endpoint (`/verify/<token>`) displaying authenticated student details, active/expired status, issue date, expiry date, and verification scan counters.
- Protects student privacy by not exposing unnecessary personal or medical data to unauthorized viewers.

### 7. Print Queue & Manifest
- Track cards as *Pending* or *Printed*.
- Single or bulk "Mark as Printed" status updates.
- Selective reprint tracking.

### 8. Backup & Maintenance
- 1-click full system backup generating a timestamped `.zip` containing the SQLite database (`school_id_system.db`) and all photo/logo assets.
- 1-click archive restoration.
- Comprehensive audit trail recording user and system actions with timestamps.

---

## 🛠️ Technology Stack

- **Backend**: Python 3.8+ / Flask
- **Database**: SQLite (persistent storage in `./storage/` or system `APPDATA`)
- **ORM**: SQLAlchemy
- **Excel & CSV Processing**: openpyxl, Python CSV
- **Image Processing**: Pillow (300 DPI high-resolution rendering)
- **PDF Generation**: ReportLab (exact CR80 85.60 × 53.98 mm & A4 grids)
- **QR Codes**: qrcode
- **Frontend**: Bootstrap 5, FontAwesome 6, Vanilla CSS & JavaScript, HTML5 Canvas / MediaDevices Webcam Capture
- **Testing**: pytest

---

## 🚀 Getting Started

### 1. Installation
Clone or navigate to the directory and ensure dependencies are installed:
```bash
pip install -r requirements.txt
```

### 2. Running the Application
```bash
python app.py
```
Open your browser at:
```
http://127.0.0.1:5000/
```

### Camera access from another device (LAN HTTPS)
Browsers block camera access on plain HTTP LAN addresses such as `http://192.168.0.105:5000`. To use the camera from a phone or another computer, start the development server with a locally trusted certificate that includes the server's LAN IP address. On Windows, install [mkcert](https://github.com/FiloSottile/mkcert), then run these commands in PowerShell from the project directory (replace the IP if the server address changes):

```powershell
mkcert -install
mkcert -cert-file dev-cert.pem -key-file dev-key.pem 192.168.0.105 localhost 127.0.0.1
$env:APP_TLS_CERT = "$PWD\dev-cert.pem"
$env:APP_TLS_KEY = "$PWD\dev-key.pem"
python app.py
```

Open `https://192.168.0.105:5000/` on the server computer. For a phone or other device, install and trust the mkcert local root certificate on that device as well; camera access will not work if the certificate is untrusted or does not match the URL. The certificate and key are local development credentials and must not be shared or committed. Clear `APP_TLS_CERT` and `APP_TLS_KEY` in PowerShell to return to HTTP.

### Public onboarding address and enrollment period
In **School Settings → Self-Onboarding & Shared Link**, set each school's **Public IP Address / Domain** to the public origin students should use (for example `https://ids.example.org` or `https://203.0.113.20`). The generated share link, QR code, and onboarding poster use this mapping. Leave it blank to use the system-wide `PUBLIC_BASE_URL` environment variable, or the current request address if no system value is configured. The server must also be reachable at that address; configure DNS, hosting/proxy routing, firewall rules, and trusted HTTPS separately. Do not use a private LAN address for an internet-facing link.

Use **Activate/Deactivate Onboarding Link** to open or close submissions at the end of the enrollment period. When closed, both the public form and its submission endpoint reject requests; saved submissions remain available to administrators. Automatic approval only applies while the public link is open.

Before opening the form, use **School Settings → Manage Eligible Admission Numbers** to add the school's approved admission numbers. Public applicants must use an active listed number. Each admission is limited to one submission and one correction after a rejection; further attempts receive a school-administrator contact message. Rejected corrections update the original application instead of creating duplicate records. The public card preview uses the same CR80 image renderer as the print PDF, including the reserved verification QR token and Code-128 admission barcode. The status tracker requires the private submission reference rather than an admission number.

### 3. Default Login Credentials
- **Username**: `admin`
- **Password**: `admin123`

---

## 🧪 Running Automated Tests

Run the comprehensive automated test suite with pytest:
```bash
pytest -v
```

The test suite validates:
- Multi-school creation, color schemes, and tenant isolation
- Duplicate admission number rejection within the same school
- CR80 high-resolution rendering dimensions (1011 × 638 px at 300 DPI) and PDF generation
- Excel template creation, reading, auto-mapping, photo matching, and validation
- Cryptographic QR token verification and scan counter tracking
- Bulk generation engine and batch PDF compilation

# school_id_creation_pure_for_id
