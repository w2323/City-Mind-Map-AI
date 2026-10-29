"""Display-only sector terminology. Backend node types and IDs stay unchanged."""
import re

SECTORS={
    'RESIDENTIAL':('Residential sector','Homes, apartments and local services.'),
    'BANK':('Financial sector','Banks, jewellery shops and valuable businesses.'),
    'HOSPITAL':('Medical sector','Hospitals, clinics and pharmacies.'),
    'POLICE':('Police services sector','Police and related public-safety services.'),
    'SCHOOL':('Education sector','Schools and related education services.'),
    'INDUSTRIAL':('Industrial sector','Factories, warehouses and industrial activity.'),
    'POWER_PLANT':('Energy sector','Power generation and utility services.'),
    'AMBULANCE_DEPOT':('Medical depot sector','Ambulance and emergency support services.'),
    'EMPTY':('Open-space sector','Parks, public space or undeveloped land.'),
}


def sector_label(kind):
    return SECTORS.get(kind,(str(kind).replace('_',' ').title()+' sector',''))[0]


def sector_description(kind):
    return SECTORS.get(kind,('','Mixed sector activity.'))[1]


def sector_text(message):
    """Translate visible server messages without touching payloads or identifiers."""
    text=str(message)
    for old,new in (('nodes','sectors'),('node','sector'),('cells','sector units')):
        text=re.sub(r'\b'+old+r'\b',new,text)
        text=re.sub(r'\b'+old.title()+r'\b',new.title(),text)
        text=re.sub(r'\b'+old.upper()+r'\b',new.upper(),text)
    return text
