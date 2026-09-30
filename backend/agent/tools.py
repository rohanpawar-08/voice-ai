import json
import os
import time
import random
from typing import Dict, Any, List
from langchain_core.tools import tool
import redis

# Synchronous Redis connection helper for tools
_redis_client = None
_redis_checked = False

def get_sync_redis():
    global _redis_client, _redis_checked
    if not _redis_checked:
        _redis_checked = True
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_db = int(os.getenv("REDIS_DB", "0"))
        redis_password = os.getenv("REDIS_PASSWORD", None)
        try:
            client = redis.Redis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                password=redis_password,
                decode_responses=True,
                socket_connect_timeout=0.2,
                socket_timeout=0.2
            )
            client.ping()
            _redis_client = client
        except Exception:
            _redis_client = None
    return _redis_client

# In-memory fallback if Redis is temporarily unreachable
_IN_MEMORY_APPOINTMENTS: List[Dict[str, Any]] = [
    {
        "id": "SAI-1042",
        "patient_name": "राहुल पाटील (Rahul Patil)",
        "phone": "+91 98220 12345",
        "service": "Teeth Whitening (दात पांढरे करणे / व्हाइटनिंग)",
        "doctor": "डॉ. स्नेहा पाटील (Dr. Sneha Patil)",
        "date": "उद्या (Tomorrow)",
        "time": "11:00 AM",
        "status": "Confirmed",
        "price": "₹2,500",
        "created_at": time.time() - 3600
    },
    {
        "id": "SAI-1043",
        "patient_name": "प्रिया कुलकर्णी (Priya Kulkarni)",
        "phone": "+91 94230 67890",
        "service": "Dental Cleaning & Hygiene (दात क्लिनिंग व स्वच्छता)",
        "doctor": "डॉ. स्नेहा पाटील (Dr. Sneha Patil)",
        "date": "शुक्रवार (Friday)",
        "time": "02:00 PM",
        "status": "Confirmed",
        "price": "₹800",
        "created_at": time.time() - 7200
    }
]

CLINIC_SERVICES = {
    "cleaning": {
        "name": "Dental Cleaning & Hygiene (दात स्वच्छ करणे / क्लिनिंग)",
        "price": "₹800",
        "price_spoken": "८०० रुपये (800 Rupees)",
        "duration": "30 minutes",
        "doctor": "डॉ. स्नेहा पाटील (Dr. Sneha Patil)",
        "description": "Comprehensive scaling, plaque removal, tartar cleaning, and polishing."
    },
    "root canal": {
        "name": "Root Canal Therapy (रूट कॅनल ट्रीटमेंट)",
        "price": "₹3,500",
        "price_spoken": "३,५०० रुपये (3,500 Rupees)",
        "duration": "60 minutes",
        "doctor": "डॉ. राहुल देशमुख (Dr. Rahul Deshmukh - Endodontist Specialist)",
        "description": "Gentle, painless laser-assisted pulp therapy and root canal restoration."
    },
    "whitening": {
        "name": "Teeth Whitening (दात पांढरे करणे / व्हाईटनिंग)",
        "price": "₹2,500",
        "price_spoken": "२,५०० रुपये (2,500 Rupees)",
        "duration": "45 minutes",
        "doctor": "डॉ. स्नेहा पाटील (Dr. Sneha Patil)",
        "description": "Advanced in-clinic laser enamel brightening and cosmetic stain removal."
    },
    "checkup": {
        "name": "Consultation & Checkup (सामान्य तपासणी)",
        "price": "₹300",
        "price_spoken": "३०० रुपये (300 Rupees)",
        "duration": "20 minutes",
        "doctor": "डॉ. अमित जोशी (Dr. Amit Joshi)",
        "description": "Complete oral examination, digital intraoral inspection, and cavity screening."
    },
    "extraction": {
        "name": "Tooth Extraction (दात काढणे)",
        "price": "₹1,000",
        "price_spoken": "१,००० रुपये (1,000 Rupees)",
        "duration": "30 minutes",
        "doctor": "डॉ. राहुल देशमुख (Dr. Rahul Deshmukh)",
        "description": "Safe, painless single or impacted tooth extraction under local anesthesia."
    },
    "invisalign": {
        "name": "Clear Aligners Consultation (इनव्हिसिलाइन व ब्रेसेस सल्ला)",
        "price": "मोफत (Free ₹0 Consult)",
        "price_spoken": "मोफत (Zero Rupees)",
        "duration": "25 minutes",
        "doctor": "डॉ. अमित जोशी (Dr. Amit Joshi)",
        "description": "Full 3D intraoral digital smile scan and custom aligner consultation at zero cost."
    }
}


@tool
def check_service_info(service_name: str) -> str:
    """
    Checks pricing, treatment duration, specialist doctor, and description for clinic dental services.
    Args:
        service_name: Treatment or service keyword (e.g. 'cleaning', 'root canal', 'checkup', 'whitening', 'extraction', 'invisalign').
    """
    clean_query = service_name.lower().strip()

    # Marathi service alias mapping
    marathi_aliases = {
        "दात तपासणी": "checkup",
        "तपासणी": "checkup",
        "चेकअप": "checkup",
        "दात स्वच्छ करणे": "cleaning",
        "दात स्वच्छ": "cleaning",
        "क्लिनिंग": "cleaning",
        "क्लीनिंग": "cleaning",
        "स्वच्छता": "cleaning",
        "रूट कॅनल": "root canal",
        "व्हाईटनिंग": "whitening",
        "व्हाइटनिंग": "whitening",
        "दात पांढरे": "whitening",
        "दात काढणे": "extraction",
        "काढणे": "extraction",
        "इनव्हिसिलाइन": "invisalign",
    }
    for mr_key, en_target in marathi_aliases.items():
        if mr_key in clean_query:
            clean_query = en_target
            break

    match = None
    for key, data in CLINIC_SERVICES.items():
        if key in clean_query or clean_query in key or clean_query in data["name"].lower():
            match = data
            break

    if match:
        return json.dumps({
            "service": match["name"],
            "price": match["price"],
            "duration": match["duration"],
            "specialist": match["doctor"],
            "overview": match["description"],
            "booking_available": True
        }, ensure_ascii=False)

    # If no exact match, return list of popular clinic procedures
    return json.dumps({
        "message": f"साई स्माईल डेंटल क्लिनिक येथे सर्व आधुनिक दंत उपचार उपलब्ध आहेत. '{service_name}' संदर्भातील उपचार:",
        "available_treatments": [
            {"service": v["name"], "price": v["price"], "duration": v["duration"]}
            for v in CLINIC_SERVICES.values()
        ]
    })


@tool
def check_available_slots(date: str) -> str:
    """
    Retrieves available doctor consultation appointment times for a given date.
    Args:
        date: The requested date or relative day (e.g. 'today', 'tomorrow', 'Friday', 'next Monday', '2026-10-01').
    """
    clean_date = date.strip().capitalize()
    all_slots = ["09:30 AM", "11:00 AM", "01:30 PM", "03:00 PM", "04:30 PM"]

    r = get_sync_redis()
    booked_slots = []
    if r:
        try:
            booked_slots = list(r.smembers(f"clinic:booked_slots:{clean_date.lower()}"))
        except Exception:
            pass

    available = [s for s in all_slots if s not in booked_slots]
    if not available:
        available = ["09:00 AM (Special Slot)", "05:30 PM (Evening Reserve)"]

    return json.dumps({
        "clinic": "साई स्माईल डेंटल क्लिनिक व इम्प्लांट सेंटर (Sai Smile Dental Clinic & Implant Centre)",
        "requested_date": clean_date,
        "available_slots": available,
        "location": "शिवाजी नगर, पुणे / सातारा, महाराष्ट्र (Shivaji Nagar, Pune / Satara, Maharashtra)",
        "advice": "Please select your preferred time and provide your patient name and phone number to finalize your booking."
    }, ensure_ascii=False)


@tool
def book_appointment(patient_name: str, phone: str, date: str, time_slot: str, service: str) -> str:
    """
    Books and confirms an official dental appointment for a patient, saving it to clinic records.
    Args:
        patient_name: Full name of the patient.
        phone: Contact phone number.
        date: Date of appointment (e.g. 'Tomorrow', 'उद्या', 'Friday', 'शुक्रवार', '2026-10-02').
        time_slot: Preferred time slot (e.g. '11:00 AM', '02:00 PM').
        service: Service or treatment requested (e.g. 'Dental Cleaning', 'रूट कॅनल', 'दात तपासणी').
    """
    booking_id = f"SAI-{random.randint(1000, 9999)}"

    # Determine doctor and price with Marathi alias support
    clean_svc = service.lower().strip()
    marathi_aliases = {
        "दात तपासणी": "checkup",
        "तपासणी": "checkup",
        "चेकअप": "checkup",
        "दात स्वच्छ करणे": "cleaning",
        "दात स्वच्छ": "cleaning",
        "क्लिनिंग": "cleaning",
        "क्लीनिंग": "cleaning",
        "स्वच्छता": "cleaning",
        "रूट कॅनल": "root canal",
        "व्हाईटनिंग": "whitening",
        "व्हाइटनिंग": "whitening",
        "दात पांढरे": "whitening",
        "दात काढणे": "extraction",
        "काढणे": "extraction",
        "इनव्हिसिलाइन": "invisalign",
    }
    for mr_key, en_target in marathi_aliases.items():
        if mr_key in clean_svc:
            clean_svc = en_target
            break

    matched_svc = "Consultation & Checkup (सामान्य तपासणी)"
    doctor = "डॉ. अमित जोशी (Dr. Amit Joshi)"
    price = "₹300"

    for k, v in CLINIC_SERVICES.items():
        if k in clean_svc or clean_svc in k or clean_svc in v["name"].lower():
            matched_svc = v["name"]
            doctor = v["doctor"]
            price = v["price"]
            break

    record = {
        "id": booking_id,
        "patient_name": patient_name.strip().title(),
        "phone": phone.strip(),
        "service": matched_svc,
        "doctor": doctor,
        "date": date.strip().capitalize(),
        "time": time_slot.strip(),
        "status": "Confirmed",
        "price": price,
        "created_at": time.time(),
        "notes": "Booked via Sai Smile VoiceDesk AI Receptionist"
    }

    # Store in Redis
    r = get_sync_redis()
    if r:
        try:
            r.rpush("clinic:appointments", json.dumps(record, ensure_ascii=False))
            r.sadd(f"clinic:booked_slots:{record['date'].lower()}", record['time'])
            r.incr("clinic:stats:total_bookings")
        except Exception as e:
            _IN_MEMORY_APPOINTMENTS.append(record)
    else:
        _IN_MEMORY_APPOINTMENTS.append(record)

    return json.dumps({
        "status": "success",
        "booking_id": booking_id,
        "patient_name": record["patient_name"],
        "service": record["service"],
        "doctor": record["doctor"],
        "date": record["date"],
        "time": record["time"],
        "price": record["price"],
        "clinic_name": "साई स्माईल डेंटल क्लिनिक व इम्प्लांट सेंटर (Sai Smile Dental Clinic)",
        "clinic_address": "शिवाजी नगर, पुणे / सातारा, महाराष्ट्र",
        "confirmation_message": (
            f"आपली अपॉइंटमेंट यशस्वीरीत्या निश्चित झाली आहे! बुकिंग आयडी: {booking_id}. "
            f"{record['date']} रोजी {record['time']} वाजता {record['doctor']} यांच्याकडे {record['service']} साठी वेळ आरक्षित आहे. "
            f"फी {record['price']} असेल. साई स्माईल डेंटल क्लिनिक, शिवाजी नगर, पुणे येथे आपले स्वागत आहे! "
            f"(Appointment confirmed for {record['patient_name']} on {record['date']} at {record['time']}. Price: {record['price']})."
        )
    }, ensure_ascii=False)


def get_all_appointments() -> List[Dict[str, Any]]:
    """Helper used by FastAPI REST endpoint to fetch all booked appointments."""
    r = get_sync_redis()
    if r:
        try:
            raw_list = r.lrange("clinic:appointments", 0, -1)
            if raw_list:
                items = [json.loads(x) for x in raw_list]
                items.reverse()  # Newest first
                return items
        except Exception:
            pass
    return sorted(_IN_MEMORY_APPOINTMENTS, key=lambda x: x.get("created_at", 0), reverse=True)


AVAILABLE_TOOLS = [check_service_info, check_available_slots, book_appointment]
TOOL_MAP = {t.name: t for t in AVAILABLE_TOOLS}
