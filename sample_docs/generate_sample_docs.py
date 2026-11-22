"""Generate the six FICTIONAL demonstration policy PDFs.

Run inside the backend container (reportlab is in requirements.txt):
    docker compose exec -T backend python - < sample_docs/generate_sample_docs.py
    docker compose cp backend:/tmp/sample_docs/. sample_docs/
or locally if reportlab is installed:   python sample_docs/generate_sample_docs.py

All content is invented for an educational simulation. It is NOT a real clinical protocol and
governs administrative operations only.
"""
import os
import sys

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

OUT_DIR = os.environ.get("SAMPLE_DOCS_OUT") or (
    "/tmp/sample_docs" if os.path.exists("/.dockerenv") else os.path.dirname(os.path.abspath(sys.argv[0] if sys.argv[0] != "-" else __file__))
)

BANNER = "FICTIONAL DEMONSTRATION POLICY. NOT A REAL CLINICAL PROTOCOL. FOR EDUCATIONAL SIMULATION ONLY."
SCOPE = (
    "This document is fictional and was written for a teaching simulation of a fictional "
    "'Demo General Hospital'. It governs administrative and operational coordination only. "
    "Clinical priority, diagnosis and treatment decisions always remain with qualified clinicians "
    "and are outside the scope of this policy."
)

# Canonical operating bands used consistently across all documents.
BANDS = [
    "GREEN (Normal operations): average waiting time 30 minutes or less; 15 or fewer patients waiting; "
    "5 or more available beds; 3 or fewer waiting patients per doctor on duty; 4 or fewer waiting patients "
    "per nurse on duty; 10 or fewer pending investigation requests.",
    "AMBER (Elevated load): average waiting time 31 to 60 minutes; 16 to 30 patients waiting; 2 to 4 "
    "available beds; 4 to 6 waiting patients per doctor; 5 to 8 waiting patients per nurse; 11 to 20 "
    "pending investigation requests.",
    "RED (Surge): average waiting time above 60 minutes; more than 30 patients waiting; 1 or fewer "
    "available beds; more than 6 waiting patients per doctor; more than 8 waiting patients per nurse; "
    "more than 20 pending investigation requests.",
]

DOCS = [
    {
        "file": "01_ed_workflow_sop.pdf",
        "title": "Emergency Department Workflow SOP",
        "code": "DGH-ED-WF-001",
        "sections": [
            ("1. Purpose and scope", [
                SCOPE,
                "This SOP describes the administrative flow of a patient visit through the Emergency Department (ED) "
                "and the monitoring routines used by the nurse in charge and the duty manager.",
            ]),
            ("2. Visit stages", [
                ("b", [
                    "Arrival: the arrival timestamp is recorded by the front desk.",
                    "Registration: the visit is registered with a synthetic patient reference (format SIM-PAT-nnn) within 10 minutes of arrival under GREEN conditions.",
                    "Assessment: a clinician assesses the patient. Simulated triage categories in this system are labels used only to demonstrate data handling; they are not clinical decisions.",
                    "Investigation: requests are logged with a request timestamp and tracked until reported.",
                    "Disposition: the visit ends in discharge, admission request, or transfer, each recorded with a timestamp.",
                ]),
            ]),
            ("3. Hourly queue review", [
                "The nurse in charge reviews the queue every hour and records: patients waiting, average waiting time, maximum waiting time, available beds, staff on duty and pending investigations.",
                "The department operating level (GREEN, AMBER or RED) is determined using the bands in the Hospital Escalation Procedures (DGH-ESC-004). The level must be written on the shift board.",
                ("b", [
                    "Under GREEN conditions the review is hourly and findings are shared at the next staff huddle.",
                    "Under AMBER conditions the nurse in charge informs the duty manager within 15 minutes of the review.",
                    "Under RED conditions the review is repeated every 30 minutes and the Surge Response procedure applies.",
                ]),
            ]),
            ("4. Roles and responsibilities", [
                ("b", [
                    "Nurse in charge: owns the queue review, shift board and first-line escalation.",
                    "Duty manager: coordinates beds, staffing and investigation facilities, and escalates to the Administrator on Call.",
                    "Front desk: records arrival and registration data accurately and promptly.",
                    "Clinicians: retain sole authority over clinical priority and treatment.",
                ]),
            ]),
            ("5. Performance indicators", [
                ("b", [
                    "Target registration time: 10 minutes or less from arrival (5 minutes or less using fast-track registration at RED).",
                    "Target average waiting time: 30 minutes or less. An average above 60 minutes is classed as a RED indicator.",
                    "Every visit must have a recorded status; visits without an update for 2 hours are reviewed by the nurse in charge.",
                ]),
            ]),
        ],
    },
    {
        "file": "02_registration_admission_policy.pdf",
        "title": "Patient Registration and Admission Policy",
        "code": "DGH-REG-002",
        "sections": [
            ("1. Purpose and scope", [
                SCOPE,
                "This policy defines how visits are registered and how admission requests are passed to bed management.",
            ]),
            ("2. Registration", [
                ("b", [
                    "Every simulated visit receives a unique synthetic reference in the format SIM-PAT-nnn. Real names, phone numbers, addresses and medical record numbers must never be entered into this system.",
                    "Registration must be completed within 10 minutes of arrival under GREEN conditions.",
                    "Under RED conditions the front desk uses fast-track registration (minimum data set only) with a target of 5 minutes, and completes remaining fields once the queue has eased.",
                    "Registration corrections are made by adding an amendment record. Original entries are never overwritten.",
                ]),
            ]),
            ("3. Admission requests", [
                "When a clinician decides that a patient needs admission, the nurse in charge submits an admission request to the bed manager.",
                ("b", [
                    "The request is timestamped and joins the admission list in order of request time.",
                    "The bed manager must acknowledge the request within 10 minutes.",
                    "When 1 or fewer beds are available, the bed manager is notified immediately of every new admission request and reviews the admission list every 30 minutes.",
                    "Patients awaiting a bed remain visible on the ED queue with the status 'awaiting bed'.",
                ]),
            ]),
            ("4. Bed allocation", [
                ("b", [
                    "Beds are allocated by the bed manager based on availability and ward suitability. The ED does not self-assign inpatient beds.",
                    "A bed is considered available only after cleaning is complete and the bed record is updated.",
                    "If no bed can be allocated within 60 minutes of the request, the duty manager escalates under DGH-ESC-004.",
                ]),
            ]),
            ("5. System downtime", [
                "During system downtime staff use paper registration forms with synthetic references and enter the data once the system is restored. The duty manager records the downtime period in the shift log.",
            ]),
        ],
    },
    {
        "file": "03_investigation_workflow_guidelines.pdf",
        "title": "Investigation Workflow Guidelines",
        "code": "DGH-INV-003",
        "sections": [
            ("1. Purpose and scope", [
                SCOPE,
                "These guidelines describe how investigation requests (for example laboratory or imaging requests) are tracked and how delays are managed administratively. They do not specify which investigations are clinically appropriate.",
            ]),
            ("2. Request lifecycle", [
                ("b", [
                    "Requested: the request is logged with a request timestamp and the target investigation facility.",
                    "Scheduled: the facility confirms a slot and updates the status.",
                    "Performed: the facility records completion.",
                    "Reported: results are released to the requesting clinician and the request is closed.",
                ]),
            ]),
            ("3. Delay definitions", [
                ("b", [
                    "A routine request still pending 45 minutes after its request time is classed as delayed.",
                    "An urgent request still pending 20 minutes after its request time is classed as delayed.",
                    "Delayed requests are listed on the shift board and reviewed by the duty manager.",
                ]),
            ]),
            ("4. Backlog thresholds", [
                ("b", [
                    "Up to 10 pending requests: normal operation, GREEN indicator.",
                    "11 to 20 pending requests: AMBER indicator. The facility supervisor reviews the queue every hour and reports the expected delay to the nurse in charge.",
                    "More than 20 pending requests: RED indicator. The facility supervisor reviews the queue every 30 minutes, requests an additional technician through the on-call roster, and the duty manager is informed within 10 minutes.",
                ]),
            ]),
            ("5. Facility workload balancing", [
                "When one facility holds more than 60 percent of all pending requests, the duty manager may ask another facility with spare capacity to take compatible requests. Requests are never cancelled to reduce the backlog.",
            ]),
        ],
    },
    {
        "file": "04_hospital_escalation_procedures.pdf",
        "title": "Hospital Escalation Procedures",
        "code": "DGH-ESC-004",
        "sections": [
            ("1. Purpose and scope", [
                SCOPE,
                "This procedure defines the operating levels of the ED and the administrative escalation steps for each level.",
            ]),
            ("2. Operating levels", [
                "Each indicator is classed using the bands below. The department level is the highest level at which at least two indicators are met. A single RED indicator raises the department level to at least AMBER.",
                ("b", BANDS),
            ]),
            ("3. Actions at AMBER", [
                ("b", [
                    "The nurse in charge notifies the duty manager within 15 minutes.",
                    "The duty manager reviews pending investigations and the admission list and requests float staff from other departments within 30 minutes.",
                    "The discharge coordinator reviews discharge-ready patients every 2 hours (see DGH-DIS-005).",
                    "Queue reviews continue every hour.",
                ]),
            ]),
            ("4. Actions at RED (Surge Response)", [
                ("b", [
                    "The duty manager notifies the Administrator on Call within 10 minutes.",
                    "Staffing: activate the on-call roster and call tree for additional doctors and nurses (see DGH-RES-006).",
                    "Beds: open the surge observation area, and the discharge lounge for patients whom clinicians have already cleared for discharge.",
                    "Investigations: the facility supervisor reviews the queue every 30 minutes and requests an additional technician.",
                    "Registration: switch to fast-track registration (DGH-REG-002).",
                    "Queue reviews are repeated every 30 minutes and the Administrator on Call receives a status update every hour.",
                    "If RED persists for more than 60 minutes, the Administrator on Call informs the Executive on Call, who decides on further administrative measures such as postponing non-urgent elective activity. Clinical decisions remain with clinicians.",
                ]),
            ]),
            ("5. Stepping down", [
                ("b", [
                    "The department may step down one level only after 2 consecutive hourly reviews that meet the lower level.",
                    "A short post-surge review is completed within 24 hours and recorded by the duty manager.",
                    "Surge areas are closed and float staff are returned only after the department is confirmed GREEN.",
                ]),
            ]),
        ],
    },
    {
        "file": "05_discharge_coordination_sop.pdf",
        "title": "Patient Discharge Coordination SOP",
        "code": "DGH-DIS-005",
        "sections": [
            ("1. Purpose and scope", [
                SCOPE,
                "This SOP coordinates the administrative steps after a clinician has decided that a patient may be discharged, so that beds are released promptly.",
            ]),
            ("2. Discharge workflow", [
                ("b", [
                    "A clinician marks the patient as discharge-ready. This clinical decision is never made by the discharge coordinator.",
                    "The discharge coordinator confirms paperwork, transport and follow-up information.",
                    "Target discharge processing time is 45 minutes or less from the discharge-ready decision.",
                    "The bed is released to housekeeping immediately. The cleaning target is 20 minutes or less, after which the bed is marked available.",
                ]),
            ]),
            ("3. Coordinator rounds by operating level", [
                ("b", [
                    "GREEN: the discharge coordinator reviews discharge-ready patients every 4 hours.",
                    "AMBER: reviews every 2 hours.",
                    "RED: reviews every hour and reports the number of discharge-ready patients still occupying beds to the duty manager.",
                ]),
            ]),
            ("4. Discharge lounge", [
                ("b", [
                    "The discharge lounge is opened when 1 or fewer beds are available, or when the department is at RED.",
                    "Only patients whom a clinician has already cleared for discharge may use the lounge.",
                    "Patients are moved to the lounge to release the bed while they wait for transport or paperwork.",
                ]),
            ]),
            ("5. Recovery", [
                "During recovery (queue and bed indicators improving), the coordinator returns to the GREEN review frequency only after the department has been confirmed GREEN under DGH-ESC-004.",
            ]),
        ],
    },
    {
        "file": "06_resource_management_guidelines.pdf",
        "title": "Resource Management Guidelines",
        "code": "DGH-RES-006",
        "sections": [
            ("1. Purpose and scope", [
                SCOPE,
                "These guidelines describe how staff, beds and investigation capacity are monitored and rebalanced in the ED.",
            ]),
            ("2. Staffing ratios", [
                ("b", [
                    "Measured ratio: waiting patients divided by the number of doctors (or nurses) on duty in the ED.",
                    "Doctors: 3 or fewer waiting patients per doctor is GREEN; 4 to 6 is AMBER; more than 6 is RED.",
                    "Nurses: 4 or fewer waiting patients per nurse is GREEN; 5 to 8 is AMBER; more than 8 is RED.",
                    "These ratios trigger administrative staffing requests only. They are not clinical safe-staffing standards.",
                ]),
            ]),
            ("3. Staffing actions", [
                ("b", [
                    "AMBER: the duty manager requests float staff from other departments within 30 minutes.",
                    "RED: the duty manager activates the on-call roster and the call tree for off-duty staff, and informs the Administrator on Call.",
                    "Non-urgent administrative and teaching duties of ED staff are deferred during RED.",
                    "Staff on duty are given a protected rest break in rotation even during RED.",
                ]),
            ]),
            ("4. Bed management", [
                ("b", [
                    "Bed utilization is occupied beds divided by total beds. Above 85 percent is AMBER and above 95 percent is RED.",
                    "Available beds: 5 or more is GREEN, 2 to 4 is AMBER, 1 or fewer is RED.",
                    "At RED the surge observation area (up to 4 additional beds) may be opened, subject to staffing being available for it.",
                    "The bed manager reviews bed status every 30 minutes at RED.",
                ]),
            ]),
            ("5. Investigation capacity", [
                "More than 20 pending investigation requests is a RED indicator. The duty manager coordinates with facility supervisors under DGH-INV-003 and may request an additional technician.",
            ]),
            ("6. Return to normal", [
                "Resources are returned to their home departments, and surge beds closed, only after 2 consecutive hourly reviews at GREEN, and the duty manager records the release in the shift log.",
            ]),
        ],
    },
]


def build(doc: dict, out_dir: str) -> str:
    styles = getSampleStyleSheet()
    title = ParagraphStyle("t", parent=styles["Title"], fontSize=20, leading=24)
    banner = ParagraphStyle("b", parent=styles["BodyText"], textColor="#9b1c1c", fontName="Helvetica-Bold", fontSize=9.5, leading=12)
    h = ParagraphStyle("h", parent=styles["Heading2"], spaceBefore=12, spaceAfter=4)
    body = ParagraphStyle("p", parent=styles["BodyText"], fontSize=10.5, leading=14, spaceAfter=6)
    bullet = ParagraphStyle("bl", parent=body, leftIndent=14, bulletIndent=2, spaceAfter=3)

    def footer(canvas, d):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(2 * cm, 1.3 * cm, "FICTIONAL DEMONSTRATION DOCUMENT - FOR EDUCATIONAL SIMULATION ONLY")
        canvas.drawString(2 * cm, 0.9 * cm, f"Page {d.page}")
        canvas.restoreState()

    path = os.path.join(out_dir, doc["file"])
    pdf = SimpleDocTemplate(
        path, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
        title=doc["title"], author="Fictional Demo General Hospital (simulation)", subject=f"{doc['code']} (fictional)",
    )
    story = [
        Paragraph(doc["title"], title),
        Paragraph(f"Document code: {doc['code']} | Version 1.0 | Fictional Demo General Hospital", body),
        Paragraph(BANNER, banner),
        Spacer(1, 6),
    ]
    for i, (heading, items) in enumerate(doc["sections"]):
        if i > 0 and i % 2 == 0:
            story.append(PageBreak())
        story.append(Paragraph(heading, h))
        for item in items:
            if isinstance(item, tuple):
                story += [Paragraph(t, bullet, bulletText="•") for t in item[1]]
            else:
                story.append(Paragraph(item, body))
    pdf.build(story, onFirstPage=footer, onLaterPages=footer)
    return path


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    for d in DOCS:
        print("wrote", build(d, OUT_DIR))
