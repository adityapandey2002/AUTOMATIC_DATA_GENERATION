// Bundled mirror of backend/form_schema.py — used if /api/schema is unreachable.
// Backend remains the single source of truth (web fetches /api/schema at boot).
export const FORM_SCHEMA = {
  title_en: "Maternity Services Case Sheet",
  title_hi: "मातृत्व सेवाओं हेतु केस शीट",
  subtitle_en:
    "L1 Health Centre (PHC/APHC/HSC) · Admission Form · State Health Society, Bihar",
  subtitle_hi: "L1 स्वास्थ्य केन्द्र (PHC/APHC/HSC) · भर्ती फॉर्म · राज्य स्वास्थ्य समिति, बिहार",
  sections: [
    {
      id: "registration",
      title_en: "Registration Details",
      title_hi: "पंजीकरण विवरण",
      icon: "clipboard",
      fields: [
        { key: "mcts_rch_number", label_en: "MCTS / RCH No.", label_hi: "एमसीटीएस / आरसीएच संख्या", type: "text" },
        { key: "ipd_number", label_en: "IPD / Registration No.", label_hi: "आईपीडी / रजिस्ट्रेशन संख्या", type: "text" },
        { key: "bpl_jsy_registered", label_en: "BPL / JSY Registered", label_hi: "बीपीएल / जेएसवाई रजिस्ट्रेशन", type: "yesno" },
        { key: "aadhaar_number", label_en: "Aadhaar No.", label_hi: "आधार कार्ड संख्या", type: "text" },
        { key: "referred_from", label_en: "Referred from (place & reason)", label_hi: "कहाँ से रेफर हुई तथा कारण", type: "text", wide: true },
      ],
    },
    {
      id: "personal",
      title_en: "Personal & Contact Details",
      title_hi: "व्यक्तिगत एवं संपर्क विवरण",
      icon: "user",
      fields: [
        { key: "name", label_en: "Name", label_hi: "नाम", type: "text" },
        { key: "spouse_parent_of", label_en: "Wife / Daughter of", label_hi: "पत्नी या पुत्री", type: "text" },
        { key: "age", label_en: "Age (years)", label_hi: "उम्र", type: "number" },
        { key: "address", label_en: "Address", label_hi: "पता", type: "text", wide: true },
        { key: "block", label_en: "Block", label_hi: "ब्लॉक", type: "text" },
        { key: "district", label_en: "District", label_hi: "जिला", type: "text" },
        { key: "health_centre", label_en: "Health Centre Name", label_hi: "स्वास्थ्य केन्द्र का नाम", type: "text" },
        { key: "contact_phone", label_en: "Contact Phone No.", label_hi: "संपर्क के लिए फोन नं.", type: "text" },
        { key: "contact_phone_hc", label_en: "HC Contact Phone", label_hi: "फोन नं. (स्वास्थ्य केन्द्र)", type: "text" },
        { key: "asha_name", label_en: "ASHA Worker", label_hi: "आशा का नाम", type: "text" },
      ],
    },
    {
      id: "admission",
      title_en: "Admission & Medical Status",
      title_hi: "भर्ती एवं चिकित्सा स्थिति",
      icon: "activity",
      fields: [
        { key: "admission_date", label_en: "Admission Date", label_hi: "भर्ती की तारीख", type: "date" },
        { key: "admission_time", label_en: "Admission Time", label_hi: "भर्ती का समय", type: "time" },
        {
          key: "admission_category", label_en: "Admission Category", label_hi: "भर्ती की श्रेणी", type: "select",
          options: [
            { value: "With labour pain", en: "With labour pain", hi: "प्रसव पीड़ा के साथ" },
            { value: "Referred from other centre", en: "Referred from other centre", hi: "अन्य केन्द्र से रेफर" },
            { value: "Routine admission", en: "Routine admission", hi: "सामान्य भर्ती" },
          ],
        },
        { key: "marital_status", label_en: "Marital Status", label_hi: "वैवाहिक स्थिति", type: "text" },
        { key: "birth_attendant", label_en: "Birth Attendant Name", label_hi: "जन्म सहायक का नाम", type: "text" },
        { key: "lmp", label_en: "LMP", label_hi: "एलएमपी", type: "date" },
        { key: "edd", label_en: "EDD", label_hi: "ईडीडी", type: "date" },
        { key: "pregnancy_complication", label_en: "Came with pregnancy-related complication", label_hi: "गर्भावस्था से संबंधित जटिलता के साथ उपस्थित", type: "yesno" },
        { key: "anc_checkup_done", label_en: "ANC checkup done", label_hi: "एएनसी जांच हुई", type: "yesno" },
        { key: "anc_visits", label_en: "Number of ANC visits", label_hi: "एएनसी जांचों की संख्या", type: "number" },
        { key: "provisional_diagnosis", label_en: "Provisional Diagnosis", label_hi: "अस्थायी निदान", type: "text", wide: true },
        { key: "final_diagnosis", label_en: "Final Diagnosis", label_hi: "अंतिम निदान", type: "text", wide: true },
        { key: "contraceptive_history", label_en: "Contraceptive Use History", label_hi: "गर्भ निरोधन प्रयोग का इतिहास", type: "text", wide: true },
      ],
    },
    {
      id: "delivery",
      title_en: "Delivery & Baby Details",
      title_hi: "प्रसव और शिशु का विवरण",
      icon: "baby",
      fields: [
        {
          key: "delivery_mode", label_en: "Delivery Process", label_hi: "प्रसव की प्रक्रिया", type: "select",
          options: [
            { value: "Normal", en: "Normal", hi: "सामान्य" },
            { value: "Assisted", en: "Assisted", hi: "सहायता प्राप्त" },
            { value: "Caesarean", en: "Caesarean", hi: "सीज़ेरियन" },
            { value: "Other", en: "Other", hi: "अन्य" },
          ],
        },
        {
          key: "delivery_outcome", label_en: "Delivery Outcome", label_hi: "प्रसव का परिणाम", type: "select",
          options: [
            { value: "Live birth", en: "Live birth", hi: "जीवित" },
            { value: "Early neonatal death", en: "Early neonatal death", hi: "तुरंत का मृत जन्म" },
            { value: "Stillbirth", en: "Stillbirth", hi: "स्टिल बर्थ" },
            { value: "Macerated stillbirth", en: "Macerated stillbirth", hi: "मैसेरेटड स्टिल बर्थ" },
            { value: "Abortion", en: "Abortion", hi: "गर्भपात" },
          ],
        },
        {
          key: "babies_count", label_en: "Singleton / Twin / Multiple", label_hi: "एक / सिंगल / जुड़वा / मल्टिपल", type: "select",
          options: [
            { value: "Single", en: "Single", hi: "एक / सिंगल" },
            { value: "Twin", en: "Twin", hi: "जुड़वा" },
            { value: "Multiple", en: "Multiple", hi: "मल्टिपल" },
          ],
        },
        { key: "birth_weight_kg", label_en: "Birth Weight (kg)", label_hi: "जन्म के समय वजन (कि.ग्रा.)", type: "number" },
        { key: "preterm", label_en: "Preterm", label_hi: "प्री-टर्म", type: "yesno" },
        {
          key: "baby_sex", label_en: "Baby Sex", label_hi: "बच्चे का लिंग", type: "select",
          options: [
            { value: "Boy", en: "Boy", hi: "लड़का" },
            { value: "Girl", en: "Girl", hi: "लड़की" },
          ],
        },
        {
          key: "immunization", label_en: "Immunization", label_hi: "टीकाकरण", type: "multiselect", wide: true,
          options: [
            { value: "BCG", en: "BCG", hi: "बीसीजी" },
            { value: "OPV", en: "OPV", hi: "ओपीवी" },
            { value: "Hepatitis B", en: "Hepatitis B", hi: "हेपेटाइटिस बी" },
            { value: "Inj. Vitamin K1", en: "Inj. Vitamin K1", hi: "इंजेक्शन विटामिन K1" },
          ],
        },
      ],
    },
    {
      id: "outcome",
      title_en: "Final Outcome & Authentication",
      title_hi: "अंतिम परिणाम और प्रमाणीकरण",
      icon: "certify",
      fields: [
        {
          key: "final_outcome", label_en: "Final Outcome", label_hi: "अंतिम परिणाम", type: "select",
          options: [
            { value: "Discharge", en: "Discharge", hi: "डिस्चार्ज" },
            { value: "Referral", en: "Referral", hi: "रेफरल" },
            { value: "Death", en: "Death", hi: "मृत्यु" },
            { value: "LAMA", en: "LAMA", hi: "लामा" },
            { value: "Abortion", en: "Abortion", hi: "गर्भपात" },
          ],
        },
        { key: "final_date_time", label_en: "Date & Time", label_hi: "तारीख तथा समय", type: "text" },
        { key: "provider_name", label_en: "Service Provider Name", label_hi: "सेवा प्रदाता का नाम", type: "text" },
        { key: "provider_designation", label_en: "Designation", label_hi: "पदवी", type: "text" },
        { key: "provider_phone", label_en: "Phone No.", label_hi: "फोन नं.", type: "text" },
      ],
    },
  ],
};

export const ALL_FIELDS = FORM_SCHEMA.sections.flatMap((s) =>
  s.fields.map((f) => ({ ...f, section: s }))
);