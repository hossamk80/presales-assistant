"""
utils/ai_engine/schemas.py — مخططات الاستخراج المُهيكل — شكل ما نطلبه من النموذج.
"""


# ─── مخططات الاستخراج ─────────────────────────────────────────────────────────

COMPLIANCE_CATEGORIES = ["Technical", "Operational", "Administrative", "Legal"]


CRITICALITY_LEVELS = ["High", "Medium", "Low"]


COMPLIANCE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "requirements": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "req_id": {
                        "type": "STRING",
                        "description": "معرّف متسلسل بصيغة REQ-001",
                    },
                    "category": {"type": "STRING", "enum": COMPLIANCE_CATEGORIES},
                    "clause_reference": {
                        "type": "STRING",
                        "description": "رقم البند أو الصفحة في الكراسة، أو نص فارغ",
                    },
                    "requirement_summary": {
                        "type": "STRING",
                        "description": "ملخّص المتطلب كما ورد في الكراسة",
                    },
                    "criticality": {"type": "STRING", "enum": CRITICALITY_LEVELS},
                    "proposed_compliance_strategy": {
                        "type": "STRING",
                        "description": "كيف يستوفي عرضنا هذا المتطلب",
                    },
                    "mandatory": {
                        "type": "BOOLEAN",
                        "description": "هل عدم استيفائه يؤدي للاستبعاد الفوري؟",
                    },
                    "certificate": {
                        "type": "STRING",
                        "description": "الشهادة أو الوثيقة المطلوبة لإثباته، أو نص فارغ",
                    },
                },
                "required": [
                    "req_id", "category", "requirement_summary",
                    "criticality", "proposed_compliance_strategy",
                ],
            },
        }
    },
    "required": ["requirements"],
}


BOQ_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "items": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "item_number": {
                        "type": "STRING",
                        "description": "الرقم التسلسلي أو رمز البند كما ورد في المصدر",
                    },
                    "category": {
                        "type": "STRING",
                        "description": "التصنيف عالي المستوى للبند",
                    },
                    "item_name": {"type": "STRING", "description": "عنوان مختصر للبند"},
                    "unit": {
                        "type": "STRING",
                        "description": "وحدة القياس: وحدة/شهر/خدمة/مقطوعية/قطعة …",
                    },
                    "description": {"type": "STRING", "description": "الوصف الفني الكامل"},
                    "specifications": {
                        "type": "STRING",
                        "description": "المواصفات الفنية التفصيلية والمعايير",
                    },
                    "construction_code": {
                        "type": "STRING",
                        "description": "كود البناء القياسي أو المرجع الكتالوجي",
                    },
                    "quantity": {"type": "NUMBER"},
                    # الكمية وحدها لا تكفي: رقمٌ منقولٌ من صفحة في الكرّاس
                    # ورقمٌ اشتقّه النموذج من فرضية لا يُقرآن سواءً، والثاني
                    # لا يخرج في العرض حتى يعتمده إنسان.
                    "quantity_source": {
                        "type": "STRING",
                        "enum": ["stated", "derived"],
                        "description": (
                            "stated إذا وردت الكمية صراحةً في المستندات، "
                            "derived إذا اشتققتَها حساباً من أرقام أخرى فيها."
                        ),
                    },
                    "quantity_basis": {
                        "type": "STRING",
                        "description": (
                            "إلزامي مع derived: المعادلة ومن أين جاء كل رقم "
                            "فيها مع مرجع الصفحة أو البند. "
                            "مثال: «نقطة شبكة لكل موظف · 500 موظف (بند 3-2)». "
                            "اتركه فارغاً مع stated."
                        ),
                    },
                    "mandatory_list_flag": {
                        "type": "BOOLEAN",
                        "description": (
                            "هل يقع هذا المنتج/الخدمة ضمن القائمة الإلزامية للمحتوى "
                            "المحلي السعودي؟ ضع true فقط عند ورود ما يدل على ذلك "
                            "في مستندات المنافسة أو في القائمة المرجعية المرفقة."
                        ),
                    },
                },
                "required": ["item_name", "unit", "quantity", "quantity_source",
                             "mandatory_list_flag"],
            },
        }
    },
    "required": ["items"],
}


PROJECT_CONTEXT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "project_title": {"type": "STRING"},
        "issuing_entity": {"type": "STRING", "description": "الجهة الحكومية أو الخاصة المصدِرة"},
        "submission_deadline": {"type": "STRING"},
        # مدة العقد سقفٌ يُقاس عليه الجدول الزمني: خطة تتجاوزها غير قابلة
        # للتنفيذ مهما حسُنت، ولجنة الفحص تردّها.
        "contract_duration": {
            "type": "STRING",
            "description": (
                "مدة تنفيذ العقد كما وردت نصاً (مثال: «اثنا عشر شهراً» أو "
                "«365 يوماً»). اكتب «غير محدد في المرفقات» إن لم ترد."
            ),
        },
        # سريان العرض والضمان الابتدائي موعدان يُغفَلان فيسقط العرض شكلياً
        # وهو مكتمل فنياً.
        "offer_validity": {
            "type": "STRING",
            "description": "مدة سريان العرض المطلوبة كما وردت، أو «غير محدد في المرفقات»",
        },
        "bid_bond": {
            "type": "STRING",
            "description": (
                "شرط الضمان الابتدائي كما ورد: نسبته ومدة سريانه وصيغته. "
                "لا تكتب مبلغاً مقدَّراً من عندك."
            ),
        },
        "scope_summary": {"type": "STRING"},
        "key_deliverables": {"type": "ARRAY", "items": {"type": "STRING"}},
        "technical_constraints": {"type": "ARRAY", "items": {"type": "STRING"}},
        "contractual_penalties": {"type": "ARRAY", "items": {"type": "STRING"}},
        "required_certifications": {"type": "ARRAY", "items": {"type": "STRING"}},
        "local_content_requirements": {"type": "STRING"},
    },
    "required": [
        "project_title", "issuing_entity", "submission_deadline", "scope_summary",
        "key_deliverables", "technical_constraints", "contractual_penalties",
        "required_certifications", "local_content_requirements",
    ],
}


# الجدول الزمني — قسم إلزامي كان يخرج نصاً حراً بلا مراحل ولا اعتماديات ولا
# معالم قابلة للتحقق، فلا يُقاس على مدة العقد ولا يُرسم.
#
# `payment_milestone` علامة **لا مبلغ**: تخدم الفريق التجاري داخل النظام،
# و**تُستبعد من المخرَج الفني** — الفني والمالي مظروفان منفصلان.
TIMELINE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "contract_duration_weeks": {
            "type": "INTEGER",
            "description": (
                "مدة العقد بالأسابيع كما تفهمها من الكراسة. ضع 0 إن لم تُذكر — "
                "لا تُقدّرها من عندك."
            ),
        },
        "phases": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "phase_number": {"type": "INTEGER", "description": "ترتيب المرحلة بدءاً من 1"},
                    "phase_name": {"type": "STRING"},
                    "start_week": {
                        "type": "INTEGER",
                        "description": "أسبوع البداية نسبةً إلى بدء العقد (الأسبوع 1 = أول أسبوع)",
                    },
                    "duration_weeks": {"type": "INTEGER", "description": "مدة المرحلة بالأسابيع"},
                    "depends_on": {
                        "type": "STRING",
                        "description": "أرقام المراحل السابقة التي تعتمد عليها، مفصولة بفاصلة. فارغ إن لا اعتمادية.",
                    },
                    "deliverables": {
                        "type": "STRING",
                        "description": "تسليمات هذه المرحلة كما تشترطها الكراسة",
                    },
                    "payment_milestone": {
                        "type": "BOOLEAN",
                        "description": "هل تنتهي المرحلة بمعلم دفع؟ علامة فقط بلا أي مبلغ أو نسبة.",
                    },
                    "weight_percent": {
                        "type": "NUMBER",
                        "description": "وزن **الإنجاز** لهذه المرحلة من 100 — نسبة تقدّم لا نسبة دفع.",
                    },
                },
                "required": ["phase_number", "phase_name", "start_week", "duration_weeks"],
            },
        },
    },
    "required": ["phases"],
}


# الأقسام الإلزامية وفق معايير الشراء الحكومي السعودي (اعتماد).
#
# المنهجية منفصلة عن الجدول الزمني عمداً: خلطهما يُنتج قسماً يصف "كيف" و"متى"
# معاً فيضعف الاثنان، بينما تُقيّمهما لجان اعتماد بمعيارين مستقلين.
#
# المحتوى المحلي ليس ضمن الستة القياسية لكنه إلزامي في المنافسات السعودية وله
# وزن في التقييم — حذفه يُفقد درجات لا يعوّضها حسن الصياغة.
MANDATORY_OUTLINE_SECTIONS = [
    "الملخص التنفيذي",
    "ملف الشركة والخبرات ذات الصلة",
    "المنهجية الفنية المقترحة وخطة التنفيذ",
    "الجدول الزمني ومعالم التسليم",
    "الهيكل التنظيمي والكوادر الرئيسية",
    "ضمان الجودة وإدارة مستويات الخدمة",
    "الالتزام بالمحتوى المحلي",
]


OUTLINE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "proposal_title": {
            "type": "STRING",
            "description": "عنوان العرض الفني المقترح لهذه المنافسة",
        },
        "outline": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "section_id": {
                        "type": "INTEGER",
                        "description": "ترتيب القسم في المستند، بدءاً من 1",
                    },
                    "section_title": {"type": "STRING", "description": "عنوان القسم"},
                    "purpose": {
                        "type": "STRING",
                        "description": "وصف موجز لما يجب أن يغطيه هذا القسم",
                    },
                    "key_points_to_address": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"},
                        "description": "النقاط الجوهرية الواجب تناولها في هذا القسم",
                    },
                    "priority": {"type": "STRING", "enum": ["عالية", "متوسطة", "منخفضة"]},
                },
                "required": [
                    "section_id", "section_title", "purpose", "key_points_to_address",
                ],
            },
        },
    },
    "required": ["proposal_title", "outline"],
}


# مستندات المظروف: ما يجب إرفاقه حتى يُقبل العرض شكلياً.
SUBMISSION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "documents": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "document": {
                        "type": "STRING",
                        "description": "اسم المستند كما تسمّيه الكراسة",
                    },
                    "clause_reference": {
                        "type": "STRING",
                        "description": "رقم البند الذي اشترطه، أو فارغ إن لم يُذكر",
                    },
                    "mandatory": {
                        "type": "BOOLEAN",
                        "description": (
                            "true إذا كان غيابه سبب استبعاد، false إن كان مُحسِّناً "
                            "أو مطلوباً عند الترسية فقط."
                        ),
                    },
                    "notes": {
                        "type": "STRING",
                        "description": (
                            "شرط خاص بالمستند: مدة سريان، جهة إصدار، صيغة، "
                            "نسبة، تصديق."
                        ),
                    },
                },
                "required": ["document", "mandatory"],
            },
        },
    },
    "required": ["documents"],
}


# مصفوفة التتبّع: ربط كل متطلب بالقسم الذي عالجه فعلاً في نص العرض.
TRACEABILITY_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "coverage": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "req_id": {
                        "type": "STRING",
                        "description": "معرّف المتطلب كما ورد حرفياً في المصفوفة",
                    },
                    "status": {
                        "type": "STRING",
                        "enum": ["مغطّى", "جزئي", "غير مغطّى"],
                        "description": (
                            "مغطّى: عولج المتطلب صراحةً وبما يكفي. "
                            "جزئي: ذُكر دون استيفاء. "
                            "غير مغطّى: لا أثر له في نص العرض."
                        ),
                    },
                    "sections": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"},
                        "description": (
                            "عناوين الأقسام التي عالجته حرفياً كما وردت في "
                            "قائمة الأقسام. فارغة إن كان غير مغطّى."
                        ),
                    },
                    "evidence": {
                        "type": "STRING",
                        "description": (
                            "اقتباس قصير من نص العرض يُثبت التغطية. "
                            "لا تكتب اقتباساً غير موجود حرفياً في النص."
                        ),
                    },
                    "gap": {
                        "type": "STRING",
                        "description": (
                            "ما الناقص تحديداً في حالتَي جزئي وغير مغطّى. "
                            "اتركه فارغاً إن كان مغطّى."
                        ),
                    },
                },
                "required": ["req_id", "status", "sections"],
            },
        },
    },
    "required": ["coverage"],
}


# مصفوفة الكوادر الرئيسية (12-2): دور تشترطه الكراسة ← المرشّح من سجل
# الكوادر ← دليل المطابقة ← الفجوة. الدور بلا مرشّح فجوة صريحة لا صمت.
KEY_PERSONNEL_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "roles": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "required_role": {
                        "type": "STRING",
                        "description": "الدور كما تشترطه الكراسة حرفياً",
                    },
                    "clause_reference": {
                        "type": "STRING",
                        "description": "رقم البند الذي اشترط الدور، أو نص فارغ",
                    },
                    "requirements": {
                        "type": "STRING",
                        "description": (
                            "ما تشترطه الكراسة في شاغل الدور: سنوات الخبرة، "
                            "الشهادات، اللغة، التفرّغ."
                        ),
                    },
                    "candidate": {
                        "type": "STRING",
                        "description": (
                            "اسم المرشّح من سجل كوادر الشركة حرفياً كما ورد "
                            "فيه. اتركه فارغاً إن لم يوجد في السجل من يطابق — "
                            "**لا تخترع اسماً ولا تقترح توظيفاً**."
                        ),
                    },
                    "evidence": {
                        "type": "STRING",
                        "description": (
                            "ما في صف المرشّح يُثبت المطابقة: سنوات خبرته "
                            "وشهاداته كما وردت في السجل. فارغ إن لا مرشّح."
                        ),
                    },
                    "gap": {
                        "type": "STRING",
                        "description": (
                            "الفجوة تحديداً: لا مرشّح، أو سنوات أقل، أو شهادة "
                            "ناقصة أو منتهية، أو إتاحة غير كافية. "
                            "اتركه فارغاً عند المطابقة التامة."
                        ),
                    },
                },
                "required": ["required_role", "requirements"],
            },
        },
    },
    "required": ["roles"],
}


REVIEW_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "readiness_score": {
            "type": "INTEGER",
            "description": (
                "درجة جاهزية العرض من زاويتك من 0 إلى 100. "
                "دون 60 يعني غير جاهز للتسليم."
            ),
        },
        "assessment": {
            "type": "STRING",
            "description": "تقييم موجز في سطرين لحالة العرض من زاويتك",
        },
        "strengths": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "description": (
                "نقاط القوة الفعلية في العرض من زاويتك. "
                "لا تُدرج مجاملات عامة — كل نقطة تشير إلى شيء مكتوب في العرض."
            ),
        },
        "recommendations": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "description": "توصيات قابلة للتنفيذ مرتّبة حسب الأثر",
        },
        "findings": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "section": {
                        "type": "STRING",
                        "description": "اسم القسم الذي تنطبق عليه الملاحظة",
                    },
                    "severity": {"type": "STRING", "enum": ["حرجة", "متوسطة", "طفيفة"]},
                    "issue": {"type": "STRING", "description": "وصف المشكلة"},
                    "impact": {
                        "type": "STRING",
                        "description": "أثرها على تقييم العرض أو قبوله",
                    },
                    "suggested_text": {
                        "type": "STRING",
                        "description": (
                            "الصياغة أو الإضافة المقترحة لمعالجة الملاحظة. "
                            "اتركه فارغاً إن كانت المعالجة تتطلب قراراً بشرياً "
                            "أو معلومة لا تملكها."
                        ),
                    },
                },
                "required": ["section", "severity", "issue", "impact"],
            },
        }
    },
    "required": [
        "readiness_score", "assessment", "strengths", "recommendations", "findings",
    ],
}
