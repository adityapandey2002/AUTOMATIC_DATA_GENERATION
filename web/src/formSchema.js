// AUTO-GENERATED from backend/form_schema.py — do not edit by hand.
// Regenerate: cd backend && venv\Scripts\python.exe export_schema_js.py
// Bundled mirror used if /api/schema is unreachable; backend is the source of truth.
export const FORM_SCHEMA = {
  "title_en": "Maternity Services Case Sheet (L3)",
  "title_hi": "मातृत्व सेवाओं हेतु केस शीट (L3)",
  "subtitle_en": "State Health Society, Bihar · L3 Case Sheet · Scribe auto-fill",
  "subtitle_hi": "राज्य स्वास्थ्य समिति, बिहार · एल3 केस शीट · स्क्राइब ऑटो-फिल",
  "sections": [
    {
      "id": "cover",
      "title_en": "Case Sheet Cover",
      "title_hi": "केस शीट (L3)",
      "icon": "clipboard",
      "fields": [
        {
          "key": "name",
          "label_en": "Beneficiary Name",
          "label_hi": "लाभार्थी का नाम",
          "type": "text",
          "wide": true
        },
        {
          "key": "registration_number",
          "label_en": "Registration No.",
          "label_hi": "पंजीकरण संख्या",
          "type": "text"
        },
        {
          "key": "husband_name",
          "label_en": "Husband's Name",
          "label_hi": "पति का नाम",
          "type": "text"
        }
      ]
    },
    {
      "id": "admission",
      "title_en": "Admission Form",
      "title_hi": "भर्ती फॉर्म",
      "icon": "clipboard",
      "fields": [
        {
          "key": "rch_number",
          "label_en": "RCH No.",
          "label_hi": "आरसीएच संख्या",
          "type": "text"
        },
        {
          "key": "health_centre",
          "label_en": "Health Centre Name",
          "label_hi": "स्वास्थ्य केन्द्र का नाम",
          "type": "text"
        },
        {
          "key": "block",
          "label_en": "Block",
          "label_hi": "ब्लॉक",
          "type": "text"
        },
        {
          "key": "district",
          "label_en": "District",
          "label_hi": "जिला",
          "type": "text"
        },
        {
          "key": "ipd_number",
          "label_en": "IPD / Registration",
          "label_hi": "आईपीडी / रजिस्ट्रेशन",
          "type": "text"
        },
        {
          "key": "bpl_jsy_registered",
          "label_en": "BPL / JSY",
          "label_hi": "बीपीएल / जेएसवाई",
          "type": "yesno"
        },
        {
          "key": "contact_phone_hc",
          "label_en": "Contact Phone (Centre)",
          "label_hi": "संपर्क फोन नं (केन्द्र)",
          "type": "text"
        },
        {
          "key": "anc_visits",
          "label_en": "No. of ANC Visits",
          "label_hi": "प्रसव पूर्व जाँच की संख्या",
          "type": "number"
        },
        {
          "key": "aadhaar_number",
          "label_en": "Aadhaar Card No.",
          "label_hi": "आधार कार्ड संख्या",
          "type": "text"
        },
        {
          "key": "asha_name",
          "label_en": "ASHA Name",
          "label_hi": "आशा का नाम",
          "type": "text"
        }
      ]
    },
    {
      "id": "patient",
      "title_en": "Patient Details & Admission",
      "title_hi": "रोगी का विवरण एवं भर्ती",
      "icon": "user",
      "fields": [
        {
          "key": "name",
          "label_en": "Name",
          "label_hi": "नाम",
          "type": "text"
        },
        {
          "key": "age",
          "label_en": "Age (years)",
          "label_hi": "उम्र",
          "type": "number"
        },
        {
          "key": "spouse_parent_of",
          "label_en": "Wife / Daughter of",
          "label_hi": "पत्नी या पुत्री",
          "type": "text"
        },
        {
          "key": "address",
          "label_en": "Address",
          "label_hi": "पता",
          "type": "text",
          "wide": true
        },
        {
          "key": "contact_phone",
          "label_en": "Contact Phone No.",
          "label_hi": "संपर्क फोन नं",
          "type": "text"
        },
        {
          "key": "marital_status",
          "label_en": "Marital Status",
          "label_hi": "वैवाहिक स्थिति",
          "type": "text"
        },
        {
          "key": "admission_date",
          "label_en": "Admission Date",
          "label_hi": "भर्ती की तारीख",
          "type": "date"
        },
        {
          "key": "admission_time",
          "label_en": "Admission Time",
          "label_hi": "समय",
          "type": "time"
        },
        {
          "key": "birth_attendant",
          "label_en": "Birth Attendant Name",
          "label_hi": "जन्म सहायक का नाम",
          "type": "text"
        },
        {
          "key": "admission_category",
          "label_en": "Admission Category",
          "label_hi": "भर्ती की श्रेणी",
          "type": "select",
          "options": [
            {
              "value": "With labour pain",
              "en": "With labour pain",
              "hi": "प्रसव पीड़ा के साथ"
            },
            {
              "value": "With pregnancy-related complication",
              "en": "With pregnancy-related complication",
              "hi": "गर्भावस्था से संबंधित जटिलता के साथ उपस्थित हुई"
            },
            {
              "value": "Referred from other centre",
              "en": "Referred from other centre",
              "hi": "अन्य केन्द्र से रेफर हुई है"
            }
          ]
        },
        {
          "key": "lmp",
          "label_en": "LMP",
          "label_hi": "एलएमपी (LMP)",
          "type": "date"
        },
        {
          "key": "edd",
          "label_en": "EDD",
          "label_hi": "ईडीडी (EDD)",
          "type": "date"
        },
        {
          "key": "provisional_diagnosis",
          "label_en": "Provisional Diagnosis",
          "label_hi": "अस्थायी निदान",
          "type": "text",
          "wide": true
        },
        {
          "key": "final_diagnosis",
          "label_en": "Final Diagnosis",
          "label_hi": "अंतिम निदान",
          "type": "text",
          "wide": true
        },
        {
          "key": "contraceptive_history",
          "label_en": "Contraceptive Use History",
          "label_hi": "गर्भ निरोधन प्रयोग का इतिहास",
          "type": "text",
          "wide": true
        }
      ]
    },
    {
      "id": "clinical",
      "title_en": "Presenting Complaints & General Examination",
      "title_hi": "मौजूदा शिकायत एवं सामान्य जाँच",
      "icon": "activity",
      "fields": [
        {
          "key": "chief_complaint",
          "label_en": "Presenting Complaints",
          "label_hi": "मौजूदा शिकायत",
          "type": "text",
          "wide": true
        },
        {
          "key": "past_obstetric_history",
          "label_en": "Past Obstetric History",
          "label_hi": "भूतपूर्व ऑब्सटेट्रिक इतिहास",
          "type": "multiselect",
          "wide": true,
          "options": [
            {
              "value": "APH",
              "en": "APH",
              "hi": "एपीएच"
            },
            {
              "value": "PPH",
              "en": "PPH",
              "hi": "पीपीएच"
            },
            {
              "value": "C-Section",
              "en": "C-Section",
              "hi": "सी-सेक्शन"
            },
            {
              "value": "Obstructed labour",
              "en": "Obstructed labour",
              "hi": "बाधित प्रसव"
            },
            {
              "value": "Still birth",
              "en": "Still birth",
              "hi": "स्टिल बर्थ"
            },
            {
              "value": "Congenital deformity",
              "en": "Congenital deformity",
              "hi": "जन्मजात विकृति"
            }
          ]
        },
        {
          "key": "medical_surgical_history",
          "label_en": "Medical / Surgical History",
          "label_hi": "मेडिकल / सर्जिकल इतिहास",
          "type": "text",
          "wide": true
        },
        {
          "key": "labour_onset_datetime",
          "label_en": "Labour Onset Date / Time",
          "label_hi": "प्रसव के शुरू होने की तारीख/समय",
          "type": "text"
        },
        {
          "key": "gravida",
          "label_en": "Gravida",
          "label_hi": "ग्रेविडा",
          "type": "number"
        },
        {
          "key": "para",
          "label_en": "Para",
          "label_hi": "पैराटी",
          "type": "number"
        },
        {
          "key": "living_children",
          "label_en": "Living Children",
          "label_hi": "जीवित बच्चे",
          "type": "number"
        },
        {
          "key": "weight_kg",
          "label_en": "Weight (kg)",
          "label_hi": "वजन",
          "type": "number"
        },
        {
          "key": "pedal_oedema",
          "label_en": "Pedal Oedema (पैरों में सूजन)",
          "label_hi": "पैरों में सूजन",
          "type": "text"
        },
        {
          "key": "temperature_c",
          "label_en": "Temperature (°C)",
          "label_hi": "तापमान",
          "type": "number"
        },
        {
          "key": "pulse_bpm",
          "label_en": "Pulse",
          "label_hi": "पल्स",
          "type": "number"
        },
        {
          "key": "bp_systolic",
          "label_en": "Blood Pressure",
          "label_hi": "ब्लड प्रेशर",
          "type": "text"
        }
      ]
    },
    {
      "id": "pa_pv_exam",
      "title_en": "Per Abdominal (PA) & Per Vaginal (PV) Examination",
      "title_hi": "पीए जाँच एवं पीवी जाँच",
      "icon": "activity",
      "fields": [
        {
          "key": "presentation",
          "label_en": "Presentation",
          "label_hi": "प्रेजेन्टेशन",
          "type": "text"
        },
        {
          "key": "engagement",
          "label_en": "Engagement",
          "label_hi": "एंगेजमेंट",
          "type": "text"
        },
        {
          "key": "gestational_age",
          "label_en": "Gestational Age",
          "label_hi": "जेस्टेशनल एज",
          "type": "text"
        },
        {
          "key": "fundal_height",
          "label_en": "Fundal Height",
          "label_hi": "फंडस की ऊंचाई",
          "type": "text"
        },
        {
          "key": "fhs",
          "label_en": "FHS",
          "label_hi": "एफएचएस (FHS)",
          "type": "text"
        },
        {
          "key": "cervical_dilation_cm",
          "label_en": "Cervical Dilation (cm)",
          "label_hi": "सर्विक्स का फैलाव (से.मी.)",
          "type": "number"
        },
        {
          "key": "cervical_effacement_pct",
          "label_en": "Cervical Effacement (%)",
          "label_hi": "सर्विक्स का एफेसमेंट (%)",
          "type": "number"
        },
        {
          "key": "station",
          "label_en": "Station",
          "label_hi": "स्टेशन",
          "type": "text"
        },
        {
          "key": "membrane",
          "label_en": "Membrane",
          "label_hi": "मेम्ब्रेन",
          "type": "select",
          "options": [
            {
              "value": "Ruptured",
              "en": "Ruptured",
              "hi": "फट गई"
            },
            {
              "value": "Intact",
              "en": "Intact",
              "hi": "साबुत"
            },
            {
              "value": "Not examined",
              "en": "Not examined",
              "hi": "नहीं"
            }
          ]
        },
        {
          "key": "amniotic_fluid_color",
          "label_en": "Amniotic Fluid Colour",
          "label_hi": "एमनियोटिक फ्लुइड का रंग",
          "type": "text"
        }
      ]
    },
    {
      "id": "investigations",
      "title_en": "Investigations",
      "title_hi": "जाँच",
      "icon": "certify",
      "fields": [
        {
          "key": "blood_group",
          "label_en": "Blood Group / Rh",
          "label_hi": "ब्लड ग्रुप / आरएच",
          "type": "text"
        },
        {
          "key": "hb_gdl",
          "label_en": "Hb (Hb)",
          "label_hi": "एचबी (Hb)",
          "type": "text"
        },
        {
          "key": "urine_sugar",
          "label_en": "Urine Sugar",
          "label_hi": "पेशाब में शुगर",
          "type": "text"
        },
        {
          "key": "hiv",
          "label_en": "HIV",
          "label_hi": "एचआईवी (HIV)",
          "type": "text"
        },
        {
          "key": "syphilis",
          "label_en": "Syphilis",
          "label_hi": "सिफलिस",
          "type": "text"
        },
        {
          "key": "hbsag",
          "label_en": "HBsAg",
          "label_hi": "एचबीएसएजी",
          "type": "text"
        }
      ]
    },
    {
      "id": "checklist1",
      "title_en": "Safe Delivery Checklist 1 (At Admission)",
      "title_hi": "सुरक्षित प्रसव जाँच सूची - 1 (भर्ती के समय)",
      "icon": "clipboard",
      "fields": [
        {
          "key": "cl1_date",
          "label_en": "Date",
          "label_hi": "तारीख",
          "type": "date"
        },
        {
          "key": "cl1_refer_mother",
          "label_en": "Mother needs referral?",
          "label_hi": "क्या माँ को रेफर करने की जरूरत है?",
          "type": "select",
          "options": [
            {
              "value": "Yes, arranged",
              "en": "Yes, arranged",
              "hi": "हाँ, व्यवस्थित किया"
            },
            {
              "value": "No",
              "en": "No",
              "hi": "नहीं"
            }
          ]
        },
        {
          "key": "cl1_partograph",
          "label_en": "Partograph started?",
          "label_hi": "पार्टोग्राफ शुरू हो चुका है?",
          "type": "select",
          "options": [
            {
              "value": "Yes",
              "en": "Yes",
              "hi": "हाँ"
            },
            {
              "value": "No, will start at 4 cm or more",
              "en": "No, will start at ≥ 4 cm",
              "hi": "नहीं, 4 सेन्टीमीटर या उससे अधिक पर शुरू होगा"
            }
          ]
        },
        {
          "key": "cl1_antibiotic",
          "label_en": "Antibiotic needed?",
          "label_hi": "क्या माँ को एन्टीबायोटिक की जरूरत है?",
          "type": "yesno"
        },
        {
          "key": "cl1_mgso4",
          "label_en": "Injection Magnesium Sulphate?",
          "label_hi": "इन्जेक्शन मैग्नीशियम सल्फेट?",
          "type": "yesno"
        },
        {
          "key": "cl1_corticosteroid",
          "label_en": "Corticosteroid?",
          "label_hi": "कोरटीकोस्टेरोइड?",
          "type": "yesno"
        },
        {
          "key": "cl1_hygience_supplies",
          "label_en": "Soap, water & gloves available?",
          "label_hi": "क्या साबुन, पानी और दस्ताने उपलब्ध हैं?",
          "type": "select",
          "options": [
            {
              "value": "Yes, wash hands each time",
              "en": "Yes, I wash hands every time before PV exam",
              "hi": "हाँ, मैं हर बार योनि की जाँच के लिए हाथ धोऊँगी"
            },
            {
              "value": "No, supplies arranged",
              "en": "No, supplies to be arranged",
              "hi": "नहीं, आपूर्ति व्यवस्थित की"
            }
          ]
        },
        {
          "key": "cl1_danger_signs",
          "label_en": "Danger Signs (tick if present)",
          "label_hi": "खतरे के लक्षण (उपस्थित हों तो टिक करें)",
          "type": "multiselect",
          "wide": true,
          "options": [
            {
              "value": "Vaginal bleeding",
              "en": "Vaginal bleeding",
              "hi": "योनि से रक्तस्राव"
            },
            {
              "value": "Severe abdominal pain",
              "en": "Severe abdominal pain",
              "hi": "पेट में तेज दर्द"
            },
            {
              "value": "Convulsions",
              "en": "Convulsions",
              "hi": "दौरा पड़ना"
            },
            {
              "value": "Severe headache or blurred vision",
              "en": "Severe headache / blurred vision",
              "hi": "तेज सिरदर्द या धुंधला दिखना"
            },
            {
              "value": "Difficulty breathing",
              "en": "Difficulty breathing",
              "hi": "साँस लेने में तकलीफ"
            }
          ]
        }
      ]
    },
    {
      "id": "partograph",
      "title_en": "Simplified Partograph",
      "title_hi": "सरलीकृत पार्टोग्राफ",
      "icon": "activity",
      "fields": [
        {
          "key": "name",
          "label_en": "Name",
          "label_hi": "नाम",
          "type": "text"
        },
        {
          "key": "husband_name",
          "label_en": "Husband's Name",
          "label_hi": "पति का नाम",
          "type": "text"
        },
        {
          "key": "registration_number",
          "label_en": "Registration No.",
          "label_hi": "पंजी. सं.",
          "type": "text"
        },
        {
          "key": "age_parity",
          "label_en": "Age / Parity",
          "label_hi": "आयु/पैरिटी",
          "type": "text"
        },
        {
          "key": "rupture_datetime",
          "label_en": "Membrane Rupture Date & Time",
          "label_hi": "गर्भाशय की थैली फटने की तिथि और समय",
          "type": "text",
          "wide": true
        },
        {
          "key": "pg_fetal_heart",
          "label_en": "Fetal heart (presentation)",
          "label_hi": "क) गर्भस्थ शिशु की स्थिति (हृदय गति)",
          "type": "text",
          "wide": true
        },
        {
          "key": "pg_cervix_progress",
          "label_en": "Labour (cervix 4-10 cm)",
          "label_hi": "ख) प्रसव (सर्विक्स 4-10 सेमी)",
          "type": "text",
          "wide": true
        },
        {
          "key": "pg_contraction",
          "label_en": "Contractions per 10 min",
          "label_hi": "ग) संकुचन प्रति 10 मिनट",
          "type": "text",
          "wide": true
        },
        {
          "key": "pg_mother_status",
          "label_en": "Mother's status (pulse, BP, temperature)",
          "label_hi": "घ) माँ की स्थिति (नाड़ी गति और रक्तचाप, तापमान)",
          "type": "text",
          "wide": true
        }
      ]
    },
    {
      "id": "doctor_notes_1",
      "title_en": "Doctor's Notes — 1",
      "title_hi": "चिकित्सक के देखने के बाद सलाह — 1",
      "icon": "certify",
      "fields": [
        {
          "key": "name",
          "label_en": "Name",
          "label_hi": "नाम",
          "type": "text"
        },
        {
          "key": "dn1_doctor",
          "label_en": "Dr.",
          "label_hi": "डॉ.",
          "type": "text"
        },
        {
          "key": "dn1_date",
          "label_en": "Date",
          "label_hi": "तारीख",
          "type": "date"
        },
        {
          "key": "dn1_time",
          "label_en": "Time",
          "label_hi": "समय",
          "type": "time"
        },
        {
          "key": "dn1_notes",
          "label_en": "Notes / Advice",
          "label_hi": "नोट्स / सलाह",
          "type": "text",
          "wide": true
        }
      ]
    },
    {
      "id": "doctor_notes_2",
      "title_en": "Doctor's Notes — 2",
      "title_hi": "चिकित्सक के देखने के बाद सलाह — 2",
      "icon": "certify",
      "fields": [
        {
          "key": "name",
          "label_en": "Name",
          "label_hi": "नाम",
          "type": "text"
        },
        {
          "key": "dn2_doctor",
          "label_en": "Dr.",
          "label_hi": "डॉ.",
          "type": "text"
        },
        {
          "key": "dn2_date",
          "label_en": "Date",
          "label_hi": "तारीख",
          "type": "date"
        },
        {
          "key": "dn2_time",
          "label_en": "Time",
          "label_hi": "समय",
          "type": "time"
        },
        {
          "key": "dn2_notes",
          "label_en": "Notes / Advice",
          "label_hi": "नोट्स / सलाह",
          "type": "text",
          "wide": true
        }
      ]
    },
    {
      "id": "doctor_notes_3",
      "title_en": "Doctor's Notes — 3",
      "title_hi": "चिकित्सक के देखने के बाद सलाह — 3",
      "icon": "certify",
      "fields": [
        {
          "key": "name",
          "label_en": "Name",
          "label_hi": "नाम",
          "type": "text"
        },
        {
          "key": "dn3_doctor",
          "label_en": "Dr.",
          "label_hi": "डॉ.",
          "type": "text"
        },
        {
          "key": "dn3_date",
          "label_en": "Date",
          "label_hi": "तारीख",
          "type": "date"
        },
        {
          "key": "dn3_time",
          "label_en": "Time",
          "label_hi": "समय",
          "type": "time"
        },
        {
          "key": "dn3_notes",
          "label_en": "Notes / Advice",
          "label_hi": "नोट्स / सलाह",
          "type": "text",
          "wide": true
        }
      ]
    },
    {
      "id": "doctor_notes_4",
      "title_en": "Doctor's Notes — 4",
      "title_hi": "चिकित्सक के देखने के बाद सलाह — 4",
      "icon": "certify",
      "fields": [
        {
          "key": "name",
          "label_en": "Name",
          "label_hi": "नाम",
          "type": "text"
        },
        {
          "key": "dn4_doctor",
          "label_en": "Dr.",
          "label_hi": "डॉ.",
          "type": "text"
        },
        {
          "key": "dn4_date",
          "label_en": "Date",
          "label_hi": "तारीख",
          "type": "date"
        },
        {
          "key": "dn4_time",
          "label_en": "Time",
          "label_hi": "समय",
          "type": "time"
        },
        {
          "key": "dn4_notes",
          "label_en": "Notes / Advice",
          "label_hi": "नोट्स / सलाह",
          "type": "text",
          "wide": true
        }
      ]
    },
    {
      "id": "doctor_notes_5",
      "title_en": "Doctor's Notes — 5",
      "title_hi": "चिकित्सक के देखने के बाद सलाह — 5",
      "icon": "certify",
      "fields": [
        {
          "key": "name",
          "label_en": "Name",
          "label_hi": "नाम",
          "type": "text"
        },
        {
          "key": "dn5_doctor",
          "label_en": "Dr.",
          "label_hi": "डॉ.",
          "type": "text"
        },
        {
          "key": "dn5_date",
          "label_en": "Date",
          "label_hi": "तारीख",
          "type": "date"
        },
        {
          "key": "dn5_time",
          "label_en": "Time",
          "label_hi": "समय",
          "type": "time"
        },
        {
          "key": "dn5_notes",
          "label_en": "Notes / Advice",
          "label_hi": "नोट्स / सलाह",
          "type": "text",
          "wide": true
        }
      ]
    },
    {
      "id": "doctor_notes_6",
      "title_en": "Doctor's Notes — 6",
      "title_hi": "चिकित्सक के देखने के बाद सलाह — 6",
      "icon": "certify",
      "fields": [
        {
          "key": "name",
          "label_en": "Name",
          "label_hi": "नाम",
          "type": "text"
        },
        {
          "key": "dn6_doctor",
          "label_en": "Dr.",
          "label_hi": "डॉ.",
          "type": "text"
        },
        {
          "key": "dn6_date",
          "label_en": "Date",
          "label_hi": "तारीख",
          "type": "date"
        },
        {
          "key": "dn6_time",
          "label_en": "Time",
          "label_hi": "समय",
          "type": "time"
        },
        {
          "key": "dn6_notes",
          "label_en": "Notes / Advice",
          "label_hi": "नोट्स / सलाह",
          "type": "text",
          "wide": true
        }
      ]
    },
    {
      "id": "consent_procedure",
      "title_en": "Consent for Procedure",
      "title_hi": "प्रक्रिया के लिए सहमति",
      "icon": "certify",
      "fields": [
        {
          "key": "name",
          "label_en": "Name (self)",
          "label_hi": "नाम (स्वयं)",
          "type": "text"
        },
        {
          "key": "consent_relative_name",
          "label_en": "Son / Daughter / Wife name",
          "label_hi": "बेटा/बेटी/पत्नी का नाम",
          "type": "text"
        },
        {
          "key": "consent_age",
          "label_en": "Age (years)",
          "label_hi": "उम्र (साल में)",
          "type": "number"
        },
        {
          "key": "consent_address",
          "label_en": "Address",
          "label_hi": "पता",
          "type": "text",
          "wide": true
        },
        {
          "key": "consent_by",
          "label_en": "Consent given by",
          "label_hi": "सहमति देने वाला",
          "type": "select",
          "options": [
            {
              "value": "Self",
              "en": "Self",
              "hi": "स्वयं"
            },
            {
              "value": "Other",
              "en": "Other",
              "hi": "अन्य"
            }
          ]
        },
        {
          "key": "consent_relationship",
          "label_en": "Relationship",
          "label_hi": "रिश्ता",
          "type": "text"
        },
        {
          "key": "consent_procedure_name",
          "label_en": "Procedure name",
          "label_hi": "प्रक्रिया का नाम",
          "type": "text",
          "wide": true
        }
      ]
    },
    {
      "id": "consent_ppiucd",
      "title_en": "PPIUCD Consent",
      "title_hi": "पीपीआईयूसीडी के लिए सहमति",
      "icon": "certify",
      "fields": [
        {
          "key": "name",
          "label_en": "Name (self)",
          "label_hi": "नाम (स्वयं)",
          "type": "text"
        },
        {
          "key": "consent_relative_name",
          "label_en": "Son / Daughter / Wife name",
          "label_hi": "बेटा/बेटी/पत्नी का नाम",
          "type": "text"
        },
        {
          "key": "consent_age",
          "label_en": "Age (years)",
          "label_hi": "उम्र (साल में)",
          "type": "number"
        },
        {
          "key": "consent_address",
          "label_en": "Address",
          "label_hi": "पता",
          "type": "text",
          "wide": true
        },
        {
          "key": "ppiucd_consent_given",
          "label_en": "Consent for PPIUCD insertion",
          "label_hi": "पीपीआईयूसीडी लगवाने की सहमति",
          "type": "yesno"
        }
      ]
    },
    {
      "id": "pre_anesthetic",
      "title_en": "Pre-Anesthetic Checkup Notes",
      "title_hi": "प्री-एनेस्थेटिक चैक-अप नोट्स",
      "icon": "activity",
      "fields": [
        {
          "key": "prean_date",
          "label_en": "Date",
          "label_hi": "तारीख",
          "type": "date"
        },
        {
          "key": "prean_time",
          "label_en": "Time",
          "label_hi": "समय",
          "type": "time"
        },
        {
          "key": "prean_planned_procedure",
          "label_en": "Planned procedure",
          "label_hi": "नियोजित प्रक्रिया",
          "type": "text",
          "wide": true
        },
        {
          "key": "prean_history",
          "label_en": "History",
          "label_hi": "इतिहास",
          "type": "text",
          "wide": true
        },
        {
          "key": "prean_cvs",
          "label_en": "CVS",
          "label_hi": "सीवीएस (CVS)",
          "type": "text",
          "wide": true
        },
        {
          "key": "prean_rs",
          "label_en": "RS",
          "label_hi": "आरएस (RS)",
          "type": "text",
          "wide": true
        },
        {
          "key": "prean_cns",
          "label_en": "CNS",
          "label_hi": "सीएनएस (CNS)",
          "type": "text",
          "wide": true
        },
        {
          "key": "prean_other",
          "label_en": "Other",
          "label_hi": "अन्य (Other)",
          "type": "text",
          "wide": true
        },
        {
          "key": "prean_investigations",
          "label_en": "Investigations",
          "label_hi": "जाँचें (Investigations)",
          "type": "text",
          "wide": true
        },
        {
          "key": "prean_orders",
          "label_en": "Orders",
          "label_hi": "आदेश (Orders)",
          "type": "text",
          "wide": true
        }
      ]
    },
    {
      "id": "anesthesia_notes",
      "title_en": "Anesthesia Notes",
      "title_hi": "एनेस्थीसिया नोट्स",
      "icon": "activity",
      "fields": [
        {
          "key": "an_date",
          "label_en": "Date",
          "label_hi": "तारीख",
          "type": "date"
        },
        {
          "key": "an_start_time",
          "label_en": "Start Time",
          "label_hi": "शुरू करने का समय",
          "type": "time"
        },
        {
          "key": "an_end_time",
          "label_en": "End Time",
          "label_hi": "अंत करने का समय",
          "type": "time"
        },
        {
          "key": "an_procedure",
          "label_en": "Procedure",
          "label_hi": "प्रक्रिया",
          "type": "text",
          "wide": true
        },
        {
          "key": "an_anesthesiologist",
          "label_en": "Anesthesiologist Name",
          "label_hi": "एनेस्थीसियोलोजिस्ट का नाम",
          "type": "text"
        },
        {
          "key": "an_nurse",
          "label_en": "Anesthesia Nurse Name",
          "label_hi": "एनेस्थीसिया नर्स का नाम",
          "type": "text"
        },
        {
          "key": "an_notes",
          "label_en": "Notes",
          "label_hi": "नोट्स",
          "type": "text",
          "wide": true
        },
        {
          "key": "an_reversal",
          "label_en": "Reversal",
          "label_hi": "रिवर्सल",
          "type": "text",
          "wide": true
        },
        {
          "key": "an_post_op_orders",
          "label_en": "Post-procedure orders",
          "label_hi": "प्रक्रिया पश्चात् आदेश",
          "type": "text",
          "wide": true
        }
      ]
    },
    {
      "id": "checklist2",
      "title_en": "Safe Delivery Checklist 2 (Just Before & During Delivery)",
      "title_hi": "सुरक्षित प्रसव जाँच सूची - 2 (प्रसव से बिल्कुल पहले और प्रसव के दौरान)",
      "icon": "clipboard",
      "fields": [
        {
          "key": "cl2_antibiotic",
          "label_en": "Antibiotic needed?",
          "label_hi": "क्या माँ को एन्टीबायोटिक की जरूरत है?",
          "type": "yesno"
        },
        {
          "key": "cl2_mgso4",
          "label_en": "Injection Magnesium Sulphate?",
          "label_hi": "इन्जेक्शन मैग्नीशियम सल्फेट?",
          "type": "yesno"
        },
        {
          "key": "cl2_skilled_assistant",
          "label_en": "Skilled assistant assigned & ready at birth",
          "label_hi": "कुशल सहायक निर्धारित है और जन्म के समय मदद के लिए तैयार है",
          "type": "yesno"
        },
        {
          "key": "cl2_mother_supplies",
          "label_en": "Labour room supplies — for mother",
          "label_hi": "लेबर रूम सामग्री — माँ के लिए",
          "type": "multiselect",
          "wide": true,
          "options": [
            {
              "value": "Gloves",
              "en": "Gloves",
              "hi": "दस्ताने"
            },
            {
              "value": "Soap and clean water",
              "en": "Soap and clean water",
              "hi": "साबुन और साफ पानी"
            },
            {
              "value": "10 units oxytocin in syringe",
              "en": "10 units oxytocin in syringe",
              "hi": "सिरिंज में 10 यूनिट ऑक्सीटोसिन"
            },
            {
              "value": "Pads for mother",
              "en": "Pads for mother",
              "hi": "माँ के लिए पैड्स"
            }
          ]
        },
        {
          "key": "cl2_baby_supplies",
          "label_en": "Labour room supplies — for baby",
          "label_hi": "लेबर रूम सामग्री — बच्चे के लिए",
          "type": "multiselect",
          "wide": true,
          "options": [
            {
              "value": "Two clean dry warm towels",
              "en": "Two clean dry warm towels",
              "hi": "दो साफ सूखे गर्म तौलिये"
            },
            {
              "value": "Sterile scissors / blade for cord",
              "en": "Sterile scissors / blade for cord cutting",
              "hi": "नाल काटने के लिए स्टराइल कैंची / ब्लेड"
            },
            {
              "value": "Mucus extractor",
              "en": "Mucus extractor",
              "hi": "म्यूकस एक्सट्रेक्टर"
            },
            {
              "value": "Cord tie / clamp",
              "en": "Cord tie / clamp",
              "hi": "नाल बाँधने का धागा / क्लैम्प"
            },
            {
              "value": "Bag and mask",
              "en": "Bag and mask",
              "hi": "बैग और मास्क"
            }
          ]
        },
        {
          "key": "cl2_amtsl_single_baby",
          "label_en": "AMTSL: confirmed only one baby",
          "label_hi": "एएमटीएसएल: केवल एक ही बच्चा है — सुनिश्चित",
          "type": "yesno"
        },
        {
          "key": "cl2_amtsl_oxytocin",
          "label_en": "AMTSL: oxytocin within 1 minute of birth",
          "label_hi": "एएमटीएसएल: जन्म के एक मिनट के अंदर ऑक्सीटोसिन",
          "type": "yesno"
        },
        {
          "key": "cl2_amtsl_traction",
          "label_en": "AMTSL: placenta delivered by controlled cord traction",
          "label_hi": "एएमटीएसएल: कन्ट्रोल्ड कॉर्ड ट्रैक्शन से ऑवल निकालना",
          "type": "yesno"
        }
      ]
    },
    {
      "id": "delivery_notes",
      "title_en": "Delivery Notes",
      "title_hi": "डिलीवरी नोट्स",
      "icon": "baby",
      "fields": [
        {
          "key": "delivery_date",
          "label_en": "Delivery Date",
          "label_hi": "प्रसव की तारीख",
          "type": "date"
        },
        {
          "key": "delivery_time",
          "label_en": "Time",
          "label_hi": "समय",
          "type": "time"
        },
        {
          "key": "delivery_mode",
          "label_en": "Delivery Method",
          "label_hi": "प्रसव का तरीका",
          "type": "select",
          "options": [
            {
              "value": "Normal",
              "en": "Normal",
              "hi": "सामान्य"
            },
            {
              "value": "Caesarean",
              "en": "LSCS",
              "hi": "एलएससीएस"
            },
            {
              "value": "Assisted",
              "en": "Assisted",
              "hi": "एसिस्टेड"
            }
          ]
        },
        {
          "key": "delivery_outcome",
          "label_en": "Outcome",
          "label_hi": "परिणाम",
          "type": "select",
          "options": [
            {
              "value": "Live birth",
              "en": "Live birth",
              "hi": "जीवित जन्म"
            },
            {
              "value": "Stillbirth",
              "en": "Still birth",
              "hi": "स्टिल बर्थ"
            }
          ]
        },
        {
          "key": "babies_count",
          "label_en": "Singleton / Twin",
          "label_hi": "एक/सिंगल / जुड़वा",
          "type": "select",
          "options": [
            {
              "value": "Single",
              "en": "Single",
              "hi": "एक/सिंगल"
            },
            {
              "value": "Twin",
              "en": "Twin",
              "hi": "जुड़वा"
            }
          ]
        },
        {
          "key": "episiotomy",
          "label_en": "Episiotomy",
          "label_hi": "एपिसियोटॉमी",
          "type": "yesno"
        },
        {
          "key": "amtsl_done",
          "label_en": "AMTSL",
          "label_hi": "एएमटीएसएल (AMTSL)",
          "type": "yesno"
        },
        {
          "key": "uterotonic_given",
          "label_en": "1. Uterotonic given",
          "label_hi": "1. दी गई यूट्रोटोनिक",
          "type": "text",
          "wide": true
        },
        {
          "key": "cct_done",
          "label_en": "2. CCT",
          "label_hi": "2. सीसीटी (CCT)",
          "type": "yesno"
        },
        {
          "key": "uterine_massage",
          "label_en": "3. Uterine massage",
          "label_hi": "3. यूटेराइन मसाज",
          "type": "yesno"
        },
        {
          "key": "delivery_complications",
          "label_en": "Complications",
          "label_hi": "जटिलताएँ",
          "type": "multiselect",
          "wide": true,
          "options": [
            {
              "value": "PPH",
              "en": "PPH",
              "hi": "पीपीएच"
            },
            {
              "value": "Sepsis",
              "en": "Sepsis",
              "hi": "सेप्सिस"
            },
            {
              "value": "PE/E",
              "en": "PE/E",
              "hi": "पीई/ई"
            },
            {
              "value": "None",
              "en": "None",
              "hi": "कोई नहीं"
            }
          ]
        },
        {
          "key": "ppiucd_inserted",
          "label_en": "PPIUCD inserted",
          "label_hi": "पीपीआईयूसीडी लगाई गई",
          "type": "yesno"
        }
      ]
    },
    {
      "id": "baby_notes",
      "title_en": "Baby Notes",
      "title_hi": "बच्चे के नोट्स",
      "icon": "baby",
      "fields": [
        {
          "key": "baby_sex",
          "label_en": "Baby Sex",
          "label_hi": "बच्चे का लिंग",
          "type": "select",
          "options": [
            {
              "value": "Boy",
              "en": "Boy",
              "hi": "लड़का"
            },
            {
              "value": "Girl",
              "en": "Girl",
              "hi": "लड़की"
            }
          ]
        },
        {
          "key": "birth_weight_kg",
          "label_en": "Birth Weight (kg)",
          "label_hi": "जन्म के समय वजन (कि.ग्रा.)",
          "type": "number"
        },
        {
          "key": "baby_cried",
          "label_en": "Baby cried immediately after birth",
          "label_hi": "क्या जन्म के तुरन्त बाद बच्चा रोया",
          "type": "yesno"
        },
        {
          "key": "baby_resuscitation",
          "label_en": "Resuscitation needed",
          "label_hi": "क्या बच्चे को रिससिटेशन की आवश्यकता पड़ी",
          "type": "yesno"
        },
        {
          "key": "breastfeeding_started",
          "label_en": "Breastfeeding started",
          "label_hi": "स्तनपान की शुरुआत हुई",
          "type": "yesno"
        },
        {
          "key": "breastfeeding_time",
          "label_en": "Time",
          "label_hi": "समय",
          "type": "time"
        },
        {
          "key": "birth_defect",
          "label_en": "Any birth defect / complication",
          "label_hi": "कोई जन्म से विकृति / जटिलता",
          "type": "text",
          "wide": true
        },
        {
          "key": "vitamin_k1",
          "label_en": "Injection Vitamin K1 given",
          "label_hi": "इंजेक्शन विटामिन K1 दिया गया",
          "type": "yesno"
        },
        {
          "key": "immunization",
          "label_en": "Immunization",
          "label_hi": "टीकाकरण",
          "type": "multiselect",
          "wide": true,
          "options": [
            {
              "value": "BCG",
              "en": "BCG",
              "hi": "बीसीजी"
            },
            {
              "value": "OPV",
              "en": "OPV",
              "hi": "ओपीवी"
            },
            {
              "value": "Hepatitis B",
              "en": "Hepatitis B",
              "hi": "हेपेटाइटिस बी"
            }
          ]
        }
      ]
    },
    {
      "id": "surgical_safety",
      "title_en": "Surgical Safety Checklist",
      "title_hi": "सर्जिकल सेफ्टी चेकलिस्ट",
      "icon": "certify",
      "fields": [
        {
          "key": "ss_before_induction",
          "label_en": "Before induction of Anaesthesia",
          "label_hi": "एनेस्थीसिया इंडक्शन से पहले",
          "type": "multiselect",
          "wide": true,
          "options": [
            {
              "value": "Identity, site, procedure, consent confirmed",
              "en": "Patient identity, site, procedure and consent confirmed",
              "hi": "रोगी की पहचान, स्थान, प्रक्रिया और सहमति की पुष्टि"
            },
            {
              "value": "Site marked",
              "en": "Site marked",
              "hi": "स्थान चिह्नित"
            },
            {
              "value": "Anaesthesia machine check complete",
              "en": "Anaesthesia machine check complete",
              "hi": "एनेस्थीसिया मशीन जाँच पूर्ण"
            },
            {
              "value": "Pulse oximeter functioning",
              "en": "Pulse oximeter functioning",
              "hi": "पल्स ऑक्सीमीटर कार्यरत"
            },
            {
              "value": "Known allergy checked",
              "en": "Known allergy?",
              "hi": "ज्ञात एलर्जी?"
            },
            {
              "value": "Difficult airway risk assessed",
              "en": "Difficult airway risk?",
              "hi": "कठिन एयरवे जोखिम?"
            }
          ]
        },
        {
          "key": "ss_before_incision",
          "label_en": "Before skin incision",
          "label_hi": "त्वचा कटने से पहले",
          "type": "multiselect",
          "wide": true,
          "options": [
            {
              "value": "Team introductions confirmed",
              "en": "All team members introduced themselves",
              "hi": "सभी टीम सदस्यों ने परिचय दिया"
            },
            {
              "value": "Name, procedure, incision site confirmed",
              "en": "Patient name, procedure and incision site confirmed",
              "hi": "रोगी का नाम, प्रक्रिया और कट स्थान की पुष्टि"
            },
            {
              "value": "Antibiotic within 60 mins",
              "en": "Antibiotic prophylaxis given within 60 mins",
              "hi": "60 मिनट के भीतर एंटीबायोटिक प्रोफिलैक्सिस"
            },
            {
              "value": "Critical events discussed",
              "en": "Anticipated critical events discussed",
              "hi": "अपेक्षित गंभीर घटनाओं पर चर्चा"
            },
            {
              "value": "Essential imaging displayed",
              "en": "Essential imaging displayed",
              "hi": "आवश्यक इमेजिंग प्रदर्शित"
            }
          ]
        },
        {
          "key": "ss_before_leaving_or",
          "label_en": "Before patient leaves OR",
          "label_hi": "रोगी के ऑपरेशन थियेटर छोड़ने से पहले",
          "type": "multiselect",
          "wide": true,
          "options": [
            {
              "value": "Procedure name confirmed",
              "en": "Nurse verbally confirms procedure name",
              "hi": "नर्स प्रक्रिया का नाम मौखिक रूप से पुष्टि करे"
            },
            {
              "value": "Instrument, sponge, needle counts complete",
              "en": "Instrument, sponge and needle counts complete",
              "hi": "उपकरण, स्पंज और सुई गणना पूर्ण"
            },
            {
              "value": "Specimen labelling",
              "en": "Specimen labelling",
              "hi": "स्पेसिमेन लेबलिंग"
            },
            {
              "value": "Equipment problems addressed",
              "en": "Equipment problems addressed",
              "hi": "उपकरण समस्याएँ सुलझाई गईं"
            },
            {
              "value": "Recovery concerns discussed",
              "en": "Key concerns for recovery discussed",
              "hi": "रिकवरी के मुख्य चिंताओं पर चर्चा"
            }
          ]
        }
      ]
    },
    {
      "id": "anesthesia_safety",
      "title_en": "Anesthesia Safety Checklist",
      "title_hi": "एनेस्थीसिया सेफ्टी चेकलिस्ट",
      "icon": "certify",
      "fields": [
        {
          "key": "as_trained_assistant",
          "label_en": "Experienced assistant available for induction?",
          "label_hi": "इंडक्शन के लिए अनुभवी प्रशिक्षित सहायक उपलब्ध?",
          "type": "select",
          "options": [
            {
              "value": "Yes",
              "en": "Yes",
              "hi": "हाँ"
            },
            {
              "value": "Not applicable",
              "en": "Not applicable",
              "hi": "लागू नहीं"
            }
          ]
        },
        {
          "key": "as_npo",
          "label_en": "No food/drink for appropriate time?",
          "label_hi": "उपयुक्त समय से भोजन/पानी बंद?",
          "type": "select",
          "options": [
            {
              "value": "Yes",
              "en": "Yes",
              "hi": "हाँ"
            },
            {
              "value": "Not applicable",
              "en": "Not applicable",
              "hi": "लागू नहीं"
            }
          ]
        },
        {
          "key": "as_iv_access",
          "label_en": "Functional IV access?",
          "label_hi": "कार्यशील आईवी एक्सेस?",
          "type": "yesno"
        },
        {
          "key": "as_tilt_table",
          "label_en": "Table can be tilted head-down?",
          "label_hi": "टेबल हेड-डाउन में झुकाई जा सकती है?",
          "type": "yesno"
        },
        {
          "key": "as_equipment",
          "label_en": "Equipment check",
          "label_hi": "उपकरण जाँच",
          "type": "multiselect",
          "wide": true,
          "options": [
            {
              "value": "Compressed gas / oxygen cylinder",
              "en": "Compressed gas / reserve oxygen cylinder",
              "hi": "संपीड़ित गैस / रिज़र्व ऑक्सीजन सिलेंडर"
            },
            {
              "value": "Vaporizers connected",
              "en": "Anesthetic vaporizers connected",
              "hi": "एनेस्थेटिक वेपोराइज़र कनेक्टेड"
            },
            {
              "value": "Breathing system assembled",
              "en": "Breathing system securely assembled",
              "hi": "श्वसन प्रणाली सुरक्षित रूप से जोड़ी गई"
            },
            {
              "value": "Breathing circuits clean",
              "en": "Breathing circuits clean",
              "hi": "श्वसन सर्किट साफ"
            },
            {
              "value": "Resuscitation equipment ready",
              "en": "Resuscitation equipment present and working",
              "hi": "पुनर्जीवन उपकरण उपलब्ध और कार्यरत"
            },
            {
              "value": "Laryngoscope, tubes ready",
              "en": "Laryngoscope, tracheal tubes ready",
              "hi": "लैरिंगोस्कोप, ट्रेकियल ट्यूब तैयार"
            },
            {
              "value": "Needles and syringes sterile",
              "en": "Needles and syringes sterile",
              "hi": "सुइयाँ और सिरिंज स्टराइल"
            },
            {
              "value": "Drugs in labelled syringes",
              "en": "Drugs drawn up into labelled syringes",
              "hi": "दवाइयाँ लेबल वाली सिरिंज में"
            },
            {
              "value": "Emergency drugs present",
              "en": "Emergency drugs present in the room",
              "hi": "आपातकालीन दवाइयाँ कमरे में उपलब्ध"
            }
          ]
        }
      ]
    },
    {
      "id": "procedure_notes",
      "title_en": "Operation / Procedure Notes",
      "title_hi": "ऑपरेशन / प्रक्रिया नोट्स",
      "icon": "certify",
      "fields": [
        {
          "key": "proc_performed",
          "label_en": "Procedure performed",
          "label_hi": "की गई प्रक्रिया",
          "type": "text",
          "wide": true
        },
        {
          "key": "proc_indications",
          "label_en": "Indications for procedure",
          "label_hi": "प्रक्रिया के संकेत",
          "type": "text",
          "wide": true
        },
        {
          "key": "proc_explained",
          "label_en": "Patient/guardian explained about procedure & results",
          "label_hi": "रोगी/गार्जियन को प्रक्रिया और परिणामों के बारे में समझाया गया",
          "type": "yesno"
        },
        {
          "key": "proc_consent",
          "label_en": "Patient/guardian consent",
          "label_hi": "रोगी / गार्जियन की सहमति",
          "type": "yesno"
        },
        {
          "key": "proc_start_time",
          "label_en": "Procedure start time",
          "label_hi": "प्रक्रिया शुरू करने का समय",
          "type": "time"
        },
        {
          "key": "proc_end_time",
          "label_en": "Procedure end time",
          "label_hi": "प्रक्रिया अंत करने का समय",
          "type": "time"
        },
        {
          "key": "proc_anesthesia_type",
          "label_en": "Anesthesia type",
          "label_hi": "एनेस्थीसिया का तरीका",
          "type": "text"
        },
        {
          "key": "proc_notes",
          "label_en": "Procedure notes",
          "label_hi": "प्रक्रिया नोट्स",
          "type": "text",
          "wide": true
        },
        {
          "key": "proc_ward_condition",
          "label_en": "Condition at ward transfer",
          "label_hi": "वार्ड में भेजते समय स्थिति",
          "type": "text",
          "wide": true
        },
        {
          "key": "proc_advice",
          "label_en": "Advice for treatment",
          "label_hi": "इलाज के लिए सलाह",
          "type": "text",
          "wide": true
        }
      ]
    },
    {
      "id": "blood_transfusion",
      "title_en": "Blood Transfusion or Other Procedure Notes",
      "title_hi": "ब्लड ट्रांसफ्यूजन या अन्य प्रक्रिया के नोट्स",
      "icon": "activity",
      "fields": [
        {
          "key": "bt_notes",
          "label_en": "Notes",
          "label_hi": "नोट्स",
          "type": "text",
          "wide": true
        }
      ]
    },
    {
      "id": "checklist3",
      "title_en": "Safe Delivery Checklist 3 (Within 1 Hour After Delivery)",
      "title_hi": "सुरक्षित प्रसव जाँच सूची - 3 (प्रसव के तुरंत बाद - एक घंटे के अंदर)",
      "icon": "clipboard",
      "fields": [
        {
          "key": "cl3_excessive_bleeding",
          "label_en": "Mother having excessive bleeding?",
          "label_hi": "क्या माँ को अत्यधिक रक्तस्त्राव हो रहा है?",
          "type": "select",
          "options": [
            {
              "value": "Yes, call for help",
              "en": "Yes, call for help",
              "hi": "हाँ, सहायता के लिए पुकारें"
            },
            {
              "value": "No",
              "en": "No",
              "hi": "नहीं"
            }
          ]
        },
        {
          "key": "cl3_antibiotic_mother",
          "label_en": "Antibiotic needed (mother)?",
          "label_hi": "क्या माँ को एन्टीबायोटिक की जरूरत है?",
          "type": "yesno"
        },
        {
          "key": "cl3_mgso4",
          "label_en": "Injection Magnesium Sulphate?",
          "label_hi": "इन्जेक्शन मैग्नीशियम सल्फेट?",
          "type": "yesno"
        },
        {
          "key": "cl3_antibiotic_baby",
          "label_en": "Antibiotic needed (baby)?",
          "label_hi": "क्या बच्चे को एन्टीबायोटिक की जरूरत है?",
          "type": "yesno"
        },
        {
          "key": "cl3_referral",
          "label_en": "Referral?",
          "label_hi": "रेफरल?",
          "type": "yesno"
        },
        {
          "key": "cl3_pph_actions",
          "label_en": "If ≥ 500 ml bleeding or 1 pad soaked < 5 min",
          "label_hi": "यदि 500 मिली या अधिक रक्तस्त्राव या 1 पैड 5 मिनट से कम में भीगे",
          "type": "multiselect",
          "wide": true,
          "options": [
            {
              "value": "Call for help",
              "en": "Call for help",
              "hi": "मदद के लिए बुलाएँ"
            },
            {
              "value": "Uterine massage",
              "en": "Uterine massage",
              "hi": "गर्भाशय की मालिश करें"
            },
            {
              "value": "Start oxytocin / fluids",
              "en": "Start oxytocin / fluids",
              "hi": "ऑक्सीटोसिन / फ्लूइड शुरू करें"
            }
          ]
        },
        {
          "key": "cl3_breastfeeding",
          "label_en": "Mother has started breastfeeding",
          "label_hi": "सुनिश्चित करें कि माँ ने स्तनपान शुरू कर दिया है",
          "type": "yesno"
        }
      ]
    },
    {
      "id": "post_delivery_vitals",
      "title_en": "Post-Delivery Vitals (Mother & Baby)",
      "title_hi": "प्रसव-पश्चात स्थिति का आंकलन (माँ एवं बच्चा)",
      "icon": "activity",
      "fields": [
        {
          "key": "vitals_mother",
          "label_en": "Mother — BP / Temp / Pulse / Uterine tone / Vaginal bleeding",
          "label_hi": "माँ के लिए — रक्तचाप / तापमान / नाड़ी गति / यूटराइन टोन / योनि से रक्त स्त्राव",
          "type": "table",
          "wide": true,
          "rows": [
            {
              "key": "bp",
              "label_en": "BP",
              "label_hi": "रक्तचाप (BP)"
            },
            {
              "key": "temp",
              "label_en": "Temp",
              "label_hi": "तापमान (Temp)"
            },
            {
              "key": "pulse",
              "label_en": "Pulse",
              "label_hi": "नाड़ी गति (Pulse)"
            },
            {
              "key": "tone",
              "label_en": "Uterine tone",
              "label_hi": "यूटराइन टोन"
            },
            {
              "key": "bleeding",
              "label_en": "Vaginal bleeding",
              "label_hi": "योनि से रक्त स्त्राव"
            }
          ],
          "columns": [
            {
              "key": "m30",
              "label_en": "30 min",
              "label_hi": "30 मिनट"
            },
            {
              "key": "h1",
              "label_en": "1 hour",
              "label_hi": "1 घंटा"
            },
            {
              "key": "h2",
              "label_en": "2 hours",
              "label_hi": "2 घंटे"
            },
            {
              "key": "h4",
              "label_en": "4 hours",
              "label_hi": "4 घंटे"
            },
            {
              "key": "h6",
              "label_en": "6 hours",
              "label_hi": "6 घंटे"
            }
          ]
        },
        {
          "key": "vitals_baby",
          "label_en": "Baby — Temp / Activity / Breastfeeding",
          "label_hi": "बच्चे के लिए — तापमान / गतिविधि / स्तनपान",
          "type": "table",
          "wide": true,
          "rows": [
            {
              "key": "temp",
              "label_en": "Temp",
              "label_hi": "तापमान (Temp)"
            },
            {
              "key": "activity",
              "label_en": "Activity",
              "label_hi": "गतिविधि (Activity)"
            },
            {
              "key": "feeding",
              "label_en": "Breastfeeding",
              "label_hi": "स्तनपान कर रहा है"
            }
          ],
          "columns": [
            {
              "key": "m30",
              "label_en": "30 min",
              "label_hi": "30 मिनट"
            },
            {
              "key": "h1",
              "label_en": "1 hour",
              "label_hi": "1 घंटा"
            },
            {
              "key": "h2",
              "label_en": "2 hours",
              "label_hi": "2 घंटे"
            },
            {
              "key": "h4",
              "label_en": "4 hours",
              "label_hi": "4 घंटे"
            },
            {
              "key": "h6",
              "label_en": "6 hours",
              "label_hi": "6 घंटे"
            }
          ]
        }
      ]
    },
    {
      "id": "checklist4",
      "title_en": "Safe Delivery Checklist 4 (Before Discharge)",
      "title_hi": "सुरक्षित प्रसव जाँच सूची - 4 (छुट्टी से पहले)",
      "icon": "clipboard",
      "fields": [
        {
          "key": "cl4_bleeding_controlled",
          "label_en": "Mother's bleeding under control?",
          "label_hi": "क्या माँ का रक्तस्त्राव नियंत्रण में है?",
          "type": "select",
          "options": [
            {
              "value": "Yes",
              "en": "Yes",
              "hi": "हाँ"
            },
            {
              "value": "No, treat / refer",
              "en": "No, treat / refer",
              "hi": "नहीं, इलाज करें / रेफर करें"
            }
          ]
        },
        {
          "key": "cl4_antibiotic_mother",
          "label_en": "Antibiotic needed (mother)?",
          "label_hi": "क्या माँ को एन्टीबायोटिक की जरूरत है?",
          "type": "yesno"
        },
        {
          "key": "cl4_antibiotic_baby",
          "label_en": "Antibiotic needed (baby)?",
          "label_hi": "क्या बच्चे को एन्टीबायोटिक की जरूरत है?",
          "type": "yesno"
        },
        {
          "key": "cl4_baby_feeding",
          "label_en": "Baby breastfeeding well?",
          "label_hi": "क्या बच्चा ठीक से स्तनपान कर रहा है?",
          "type": "select",
          "options": [
            {
              "value": "Yes, exclusive breastfeeding 6 months",
              "en": "Yes — encourage exclusive breastfeeding for 6 months",
              "hi": "हाँ, माँ को 6 महीने तक सिर्फ स्तनपान कराने के लिए प्रोत्साहित करें"
            },
            {
              "value": "No, assist and delay discharge",
              "en": "No — assist and delay discharge",
              "hi": "नहीं, सहायता करें और छुट्टी में देरी करें"
            }
          ]
        },
        {
          "key": "cl4_danger_signs",
          "label_en": "Danger Signs — mother (tick if present)",
          "label_hi": "खतरे के लक्षण — माँ (उपस्थित हों तो टिक करें)",
          "type": "multiselect",
          "wide": true,
          "options": [
            {
              "value": "Excessive bleeding",
              "en": "Excessive bleeding",
              "hi": "अत्यधिक रक्तस्त्राव"
            },
            {
              "value": "Severe abdominal pain",
              "en": "Severe abdominal pain",
              "hi": "पेट में तेज दर्द"
            },
            {
              "value": "Severe headache or blurred vision",
              "en": "Severe headache / blurred vision",
              "hi": "तेज सिरदर्द या धुंधला दिखना"
            },
            {
              "value": "Difficulty breathing",
              "en": "Difficulty breathing",
              "hi": "साँस लेने में तकलीफ"
            },
            {
              "value": "Fever or chills",
              "en": "Fever or chills",
              "hi": "बुखार या सिहरन"
            }
          ]
        }
      ]
    },
    {
      "id": "discharge_notes",
      "title_en": "Discharge Notes",
      "title_hi": "डिस्चार्ज नोट्स",
      "icon": "certify",
      "fields": [
        {
          "key": "discharge_mother_condition",
          "label_en": "Mother's condition at discharge",
          "label_hi": "डिस्चार्ज के समय माँ की स्थिति",
          "type": "text",
          "wide": true
        },
        {
          "key": "final_outcome",
          "label_en": "Final Outcome",
          "label_hi": "अंतिम परिणाम",
          "type": "select",
          "options": [
            {
              "value": "Discharge",
              "en": "Discharged",
              "hi": "डिस्चार्ज हुआ"
            },
            {
              "value": "Referral",
              "en": "Referred",
              "hi": "रेफर हुआ"
            },
            {
              "value": "LAMA",
              "en": "LAMA",
              "hi": "लामा"
            },
            {
              "value": "Death",
              "en": "Maternal death",
              "hi": "मातृ मृत्यु"
            }
          ]
        },
        {
          "key": "discharge_baby_condition",
          "label_en": "Baby's condition at discharge",
          "label_hi": "डिस्चार्ज के समय बच्चे की स्थिति",
          "type": "text",
          "wide": true
        },
        {
          "key": "baby_outcome",
          "label_en": "Baby Outcome",
          "label_hi": "बच्चे का परिणाम",
          "type": "select",
          "options": [
            {
              "value": "Alive and healthy",
              "en": "Alive and healthy",
              "hi": "जीवित और स्वस्थ"
            },
            {
              "value": "Referred to SNCU",
              "en": "Referred to SNCU",
              "hi": "एसएनसीयू में रेफर हुआ"
            },
            {
              "value": "Neonatal death",
              "en": "Neonatal death",
              "hi": "नवजात मृत्यु"
            }
          ]
        },
        {
          "key": "discharge_counselling",
          "label_en": "Danger-sign counselling done",
          "label_hi": "खतरे के लक्षण के बारे में काउन्सेलिंग की गई",
          "type": "yesno"
        },
        {
          "key": "fp_method_adopted",
          "label_en": "Family planning method adopted",
          "label_hi": "परिवार नियोजन की विधि अपनाई गई",
          "type": "text",
          "wide": true
        },
        {
          "key": "fp_method",
          "label_en": "FP method",
          "label_hi": "परिवार नियोजन",
          "type": "multiselect",
          "options": [
            {
              "value": "PPIUCD",
              "en": "PPIUCD",
              "hi": "पीपीआईयूसीडी"
            },
            {
              "value": "PPS",
              "en": "PPS",
              "hi": "पीपीएस"
            },
            {
              "value": "None",
              "en": "None",
              "hi": "कोई नहीं"
            }
          ]
        }
      ]
    },
    {
      "id": "hospital_copy",
      "title_en": "Hospital Copy — Discharge / Referral Ticket",
      "title_hi": "अस्पताल की प्रति — डिस्चार्ज / रेफरल टिकट",
      "icon": "clipboard",
      "fields": [
        {
          "key": "health_centre",
          "label_en": "Health Centre Name",
          "label_hi": "स्वास्थ्य केन्द्र का नाम",
          "type": "text"
        },
        {
          "key": "hc_date",
          "label_en": "Date",
          "label_hi": "दिनांक",
          "type": "date"
        },
        {
          "key": "name",
          "label_en": "Patient Name",
          "label_hi": "रोगी का नाम",
          "type": "text"
        },
        {
          "key": "age",
          "label_en": "Age",
          "label_hi": "उम्र",
          "type": "number"
        },
        {
          "key": "husband_name",
          "label_en": "Husband's Name",
          "label_hi": "पति का नाम",
          "type": "text"
        },
        {
          "key": "ipd_number",
          "label_en": "IPD / Registration",
          "label_hi": "आईपीडी / रजिस्ट्रेशन",
          "type": "text"
        },
        {
          "key": "address",
          "label_en": "Address",
          "label_hi": "पता",
          "type": "text",
          "wide": true
        },
        {
          "key": "admission_date",
          "label_en": "Admission Date & Time",
          "label_hi": "भर्ती की तारीख व समय",
          "type": "text"
        },
        {
          "key": "delivery_date",
          "label_en": "Delivery Date & Time",
          "label_hi": "प्रसव की तारीख व समय",
          "type": "text"
        },
        {
          "key": "hc_mother_condition",
          "label_en": "Mother's condition",
          "label_hi": "माँ की स्थिति",
          "type": "text"
        },
        {
          "key": "hc_baby_condition",
          "label_en": "Baby's condition",
          "label_hi": "बच्चे की स्थिति",
          "type": "text"
        },
        {
          "key": "discharge_date",
          "label_en": "Discharge Date",
          "label_hi": "डिस्चार्ज की तारीख",
          "type": "date"
        },
        {
          "key": "hc_advice",
          "label_en": "Treatment / medicine advice (1-5)",
          "label_hi": "इलाज / दवाई की सलाह (1-5)",
          "type": "text",
          "wide": true
        }
      ]
    }
  ]
}

export const ALL_FIELDS = FORM_SCHEMA.sections.flatMap((s) =>
  s.fields.map((f) => ({ ...f, section: s }))
);
