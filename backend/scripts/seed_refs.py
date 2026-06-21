#!/usr/bin/env python3
"""
Seed script for RIS MVP.
Loads ICD-10 codes, services (tariff), creates default organization and admin user.
"""
import asyncio
import json
import os
import sys

# Add parent to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from app.core.config import get_settings
from app.core.database import Base
from app.models.organization import Organization
from app.models.user import User
from app.models.diagnosis_icd import DiagnosisICD
from app.models.service import Service
from app.models.device import Device
from app.models.protocol_template import ProtocolTemplate
from app.auth.password import hash_password

settings = get_settings()

# Use sync engine for seeding
engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def seed():
    async with AsyncSessionLocal() as session:
        # 1. Create default organization
        result = await session.execute(
            Organization.__table__.select().limit(1)
        )
        if not result.fetchone():
            org = Organization(
                name_ru=settings.DEFAULT_ORG_NAME or "Диагностический центр",
                name_kz="Диагностикалық орталық",
                license_number="Лицензия МЗ РК № 00000",
                address="г. Алматы, пр. Назарбаева, 1",
                phone="+7 (727) 123-45-67",
            )
            session.add(org)
            await session.flush()
            print(f"Created organization: {org.name_ru}")
        else:
            print("Organization already exists, skipping")
        
        # 2. Create admin user
        result = await session.execute(
            User.__table__.select().where(User.login == "admin")
        )
        if not result.fetchone():
            admin = User(
                login="admin",
                password_hash=hash_password("admin123"),
                role="ADMIN",
                last_name="Администратор",
                first_name="Системы",
                middle_name="",
                email="admin@ris.kz",
                is_active=True,
            )
            session.add(admin)
            await session.flush()
            print("Created admin user: admin / admin123")
        else:
            print("Admin user already exists, skipping")
        
        # 3. Load ICD-10 from JSON
        icd_file = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "icd10-radiology.json")
        if os.path.exists(icd_file):
            # Check if already loaded
            result = await session.execute(DiagnosisICD.__table__.select().limit(1))
            if not result.fetchone():
                with open(icd_file, "r", encoding="utf-8") as f:
                    codes = json.load(f)
                
                for code_data in codes:
                    icd = DiagnosisICD(
                        code=code_data["code"],
                        name_ru=code_data["name_ru"],
                        name_kz=code_data.get("name_kz"),
                        chapter=code_data.get("chapter"),
                        chapter_name_ru=code_data.get("chapter_name_ru"),
                        is_leaf=code_data.get("is_leaf", True),
                    )
                    session.add(icd)
                
                await session.flush()
                print(f"Loaded {len(codes)} ICD-10 codes")
            else:
                print("ICD-10 already loaded, skipping")
        else:
            print(f"ICD-10 file not found at {icd_file}, skipping")
        
        # 4. Seed services (tariff)
        result = await session.execute(Service.__table__.select().limit(1))
        if not result.fetchone():
            services_data = [
                {"code_gombp": "A06.10.001", "code_osms": "A06.10.001-О", "name_ru": "Рентгенография органов грудной клетки", "name_kz": "Кеуде қуысы мүшелерін рентгенге түсіру", "modality": "CR", "duration_min": 15, "tariff_gombp": 1800, "tariff_osms": 2100, "tariff_paid": 3500},
                {"code_gombp": "A06.20.001", "code_osms": "A06.20.001-О", "name_ru": "КТ головного мозга без контраста", "name_kz": "Бас миын КТ зерттеу", "modality": "CT", "duration_min": 20, "tariff_gombp": 8400, "tariff_osms": 9800, "tariff_paid": 18000},
                {"code_gombp": "A06.20.002", "code_osms": "A06.20.002-О", "name_ru": "КТ грудной клетки", "name_kz": "Кеуде қуысы КТ зерттеу", "modality": "CT", "duration_min": 20, "tariff_gombp": 8400, "tariff_osms": 9800, "tariff_paid": 18000},
                {"code_gombp": "A06.20.003", "code_osms": "A06.20.003-О", "name_ru": "КТ брюшной полости", "name_kz": "Іш қуысы КТ зерттеу", "modality": "CT", "duration_min": 25, "tariff_gombp": 9800, "tariff_osms": 11200, "tariff_paid": 22000},
                {"code_gombp": "A06.20.004", "code_osms": "A06.20.004-О", "name_ru": "КТ брюшной полости с контрастом", "name_kz": "Контрастпен іш қуысы КТ зерттеу", "modality": "CT", "duration_min": 35, "tariff_gombp": 13500, "tariff_osms": 15400, "tariff_paid": 30000, "contrast_agent": True},
                {"code_gombp": "A06.20.010", "code_osms": "A06.20.010-О", "name_ru": "МРТ головного мозга без контраста", "name_kz": "Бас миын МРТ зерттеу", "modality": "MR", "duration_min": 45, "tariff_gombp": 15200, "tariff_osms": 18200, "tariff_paid": 35000},
                {"code_gombp": "A06.20.011", "code_osms": "A06.20.011-О", "name_ru": "МРТ головного мозга с контрастом", "name_kz": "Контрастпен бас миын МРТ зерттеу", "modality": "MR", "duration_min": 60, "tariff_gombp": 21000, "tariff_osms": 24500, "tariff_paid": 48000, "contrast_agent": True},
                {"code_gombp": "A06.20.020", "code_osms": "A06.20.020-О", "name_ru": "МРТ позвоночника шейного отдела", "name_kz": "Мойын омыртқасы МРТ зерттеу", "modality": "MR", "duration_min": 40, "tariff_gombp": 14000, "tariff_osms": 16800, "tariff_paid": 32000},
                {"code_gombp": "A06.20.030", "code_osms": "A06.20.030-О", "name_ru": "МРТ позвоночника поясничного отдела", "name_kz": "Бел омыртқасы МРТ зерттеу", "modality": "MR", "duration_min": 40, "tariff_gombp": 14000, "tariff_osms": 16800, "tariff_paid": 32000},
                {"code_gombp": "A06.20.040", "code_osms": "A06.20.040-О", "name_ru": "МРТ коленного сустава", "name_kz": "Тізе буыны МРТ зерттеу", "modality": "MR", "duration_min": 35, "tariff_gombp": 12000, "tariff_osms": 14500, "tariff_paid": 28000},
                {"code_gombp": "A06.20.050", "code_osms": "A06.20.050-О", "name_ru": "МРТ тазобедренного сустава", "name_kz": "Жамбас-сан буыны МРТ зерттеу", "modality": "MR", "duration_min": 35, "tariff_gombp": 12000, "tariff_osms": 14500, "tariff_paid": 28000},
                {"code_gombp": "A06.20.060", "code_osms": "A06.20.060-О", "name_ru": "МРТ плечевого сустава", "name_kz": "Иық буыны МРТ зерттеу", "modality": "MR", "duration_min": 35, "tariff_gombp": 12000, "tariff_osms": 14500, "tariff_paid": 28000},
                {"code_gombp": "A06.20.070", "code_osms": "A06.20.070-О", "name_ru": "МРТ малого таза", "name_kz": "Кіші жамбас МРТ зерттеу", "modality": "MR", "duration_min": 40, "tariff_gombp": 14000, "tariff_osms": 16800, "tariff_paid": 32000},
                {"code_gombp": "A06.21.001", "code_osms": "A06.21.001-О", "name_ru": "УЗИ органов брюшной полости", "name_kz": "Іш қуысы мүшелерін УДЗ зерттеу", "modality": "US", "duration_min": 20, "tariff_gombp": 3800, "tariff_osms": 4500, "tariff_paid": 9000},
                {"code_gombp": "A06.21.002", "code_osms": "A06.21.002-О", "name_ru": "УЗИ щитовидной железы", "name_kz": "Қалқанша безін УДЗ зерттеу", "modality": "US", "duration_min": 15, "tariff_gombp": 2800, "tariff_osms": 3400, "tariff_paid": 6500},
                {"code_gombp": "A06.21.003", "code_osms": "A06.21.003-О", "name_ru": "УЗИ почек и мочевого пузыря", "name_kz": "Бүйрек пен несеп қабын УДЗ зерттеу", "modality": "US", "duration_min": 15, "tariff_gombp": 3200, "tariff_osms": 3800, "tariff_paid": 7500},
                {"code_gombp": "A06.21.004", "code_osms": "A06.21.004-О", "name_ru": "УЗИ сосудов шеи (дуплексное сканирование)", "name_kz": "Мойын қан тамырларын УДЗ зерттеу", "modality": "US", "duration_min": 25, "tariff_gombp": 5200, "tariff_osms": 6200, "tariff_paid": 12000},
                {"code_gombp": "A06.30.001", "code_osms": "A06.30.001-О", "name_ru": "Маммография обеих молочных желез", "name_kz": "Екі сүт безін маммографиялау", "modality": "MG", "duration_min": 20, "tariff_gombp": 5500, "tariff_osms": 6500, "tariff_paid": 14000},
                {"code_gombp": "A06.40.001", "code_osms": "A06.40.001-О", "name_ru": "Рентгенография черепа в 2 проекциях", "name_kz": "Бас сүйегін 2 проекцияда рентгенге түсіру", "modality": "CR", "duration_min": 15, "tariff_gombp": 2200, "tariff_osms": 2600, "tariff_paid": 5000},
                {"code_gombp": "A06.40.002", "code_osms": "A06.40.002-О", "name_ru": "Рентгенография позвоночника", "name_kz": "Омыртқаны рентгенге түсіру", "modality": "CR", "duration_min": 15, "tariff_gombp": 2400, "tariff_osms": 2800, "tariff_paid": 5500},
                {"code_gombp": "A06.40.003", "code_osms": "A06.40.003-О", "name_ru": "Рентгенография конечностей", "name_kz": "Аяқ-қолды рентгенге түсіру", "modality": "CR", "duration_min": 15, "tariff_gombp": 2000, "tariff_osms": 2400, "tariff_paid": 4500},
                {"code_gombp": "A06.50.001", "code_osms": "A06.50.001-О", "name_ru": "Флюорография", "name_kz": "Флюорография", "modality": "CR", "duration_min": 10, "tariff_gombp": 1200, "tariff_osms": 1500, "tariff_paid": 3000},
            ]
            
            for svc_data in services_data:
                svc = Service(**svc_data)
                session.add(svc)
            
            await session.flush()
            print(f"Loaded {len(services_data)} services")
        else:
            print("Services already loaded, skipping")
        
        # 5. Seed demo devices
        result = await session.execute(Device.__table__.select().limit(1))
        if not result.fetchone():
            devices_data = [
                {"name": "Siemens SOMATOM Go.All (КТ-1)", "modality_type": "CT", "ae_title": "CT1_SOMATOM", "ip_address": "192.168.1.10", "status": "ACTIVE"},
                {"name": "Philips Ingenia 3.0T (МРТ-1)", "modality_type": "MR", "ae_title": "MRI1_INGENIA", "ip_address": "192.168.1.20", "status": "ACTIVE"},
                {"name": "GE Optima MR450W (МРТ-2)", "modality_type": "MR", "ae_title": "MRI2_OPTIMA", "ip_address": "192.168.1.21", "status": "MAINTENANCE"},
                {"name": "Carestream DRX-Evolution (РГ-1)", "modality_type": "CR", "ae_title": "RG1_DRXEVOL", "ip_address": "192.168.1.30", "status": "ACTIVE"},
                {"name": "Samsung HS60 (УЗИ-1)", "modality_type": "US", "ae_title": "US1_HS60", "ip_address": "192.168.1.40", "status": "ACTIVE"},
                {"name": "Hologic Selenia (МГ-1)", "modality_type": "MG", "ae_title": "MG1_SELENIA", "ip_address": "192.168.1.50", "status": "ACTIVE"},
            ]
            
            for dev_data in devices_data:
                device = Device(**dev_data)
                session.add(device)
            
            await session.flush()
            print(f"Loaded {len(devices_data)} devices")
        else:
            print("Devices already loaded, skipping")
        
        # 6. Seed protocol templates. Add missing examples by name, even if DB already has custom templates.
        services_result = await session.execute(select(Service))
        services_by_code = {svc.code_gombp: svc for svc in services_result.scalars().all()}
        templates_data = [
            {
                "name_ru": "КТ головного мозга — норма",
                "name_kz": "Бас миының КТ — норма",
                "modality": "CT",
                "body_part": "Головной мозг",
                "service_id": services_by_code.get("A06.20.001").id if services_by_code.get("A06.20.001") else None,
                "fields_schema": [
                    {"field_key": "brain_density", "label_ru": "Плотность вещества мозга", "type": "select", "options": ["Дифференцирована", "Снижена очагово", "Диффузно изменена"], "default": "Дифференцирована"},
                    {"field_key": "hemorrhage", "label_ru": "Признаки кровоизлияния", "type": "select", "options": ["Нет", "Есть"], "default": "Нет"},
                    {"field_key": "midline_shift", "label_ru": "Смещение срединных структур", "type": "select", "options": ["Нет", "Есть"], "default": "Нет"},
                    {"field_key": "ventricles", "label_ru": "Желудочковая система", "type": "select", "options": ["Не расширена", "Расширена", "Асимметрична"], "default": "Не расширена"},
                    {"field_key": "sinuses", "label_ru": "Околоносовые пазухи", "type": "select", "options": ["Пневматизация сохранена", "Утолщение слизистой", "Жидкость"], "default": "Пневматизация сохранена"},
                ],
                "description_template": "КТ головного мозга выполнена в аксиальной плоскости с мультипланарной реконструкцией. Срединные структуры не смещены. Очаговых изменений плотности вещества мозга не выявлено. Признаков внутричерепного кровоизлияния не определяется. Желудочковая система не расширена, симметрична. Субарахноидальные пространства без особенностей. Костно-деструктивных изменений в зоне сканирования не выявлено.",
                "conclusion_template": "КТ-признаков острой внутричерепной патологии не выявлено.",
            },
            {
                "name_ru": "КТ грудной клетки — норма",
                "name_kz": "Кеуде қуысының КТ — норма",
                "modality": "CT",
                "body_part": "Грудная клетка",
                "service_id": services_by_code.get("A06.20.002").id if services_by_code.get("A06.20.002") else None,
                "fields_schema": [
                    {"field_key": "lungs", "label_ru": "Легочная ткань", "type": "select", "options": ["Без очаговых и инфильтративных изменений", "Инфильтрация", "Очаги"], "default": "Без очаговых и инфильтративных изменений"},
                    {"field_key": "pleura", "label_ru": "Плевральные полости", "type": "select", "options": ["Свободны", "Выпот справа", "Выпот слева", "Двусторонний выпот"], "default": "Свободны"},
                    {"field_key": "mediastinum", "label_ru": "Средостение", "type": "select", "options": ["Не расширено", "Расширено", "Лимфоузлы увеличены"], "default": "Не расширено"},
                    {"field_key": "heart", "label_ru": "Сердце", "type": "select", "options": ["Обычных размеров", "Увеличено"], "default": "Обычных размеров"},
                ],
                "description_template": "Легкие расправлены. Очаговых и инфильтративных изменений легочной ткани не выявлено. Бронхи прослеживаются, проходимы. Плевральные полости свободны. Средостение не смещено, не расширено. Внутригрудные лимфатические узлы не увеличены. Костные структуры без видимых деструктивных изменений.",
                "conclusion_template": "КТ-признаков очаговой или инфильтративной патологии органов грудной клетки не выявлено.",
            },
            {
                "name_ru": "МРТ головного мозга — норма",
                "name_kz": "Бас миының МРТ — норма",
                "modality": "MR",
                "body_part": "Головной мозг",
                "service_id": services_by_code.get("A06.20.010").id if services_by_code.get("A06.20.010") else None,
                "fields_schema": [
                    {"field_key": "gray_white", "label_ru": "Дифференциация серого/белого вещества", "type": "select", "options": ["Сохранена", "Нарушена"], "default": "Сохранена"},
                    {"field_key": "focal_changes", "label_ru": "Очаговые изменения", "type": "select", "options": ["Не выявлены", "Единичные", "Множественные"], "default": "Не выявлены"},
                    {"field_key": "ventricles", "label_ru": "Желудочковая система", "type": "select", "options": ["Не расширена", "Расширена"], "default": "Не расширена"},
                    {"field_key": "sellar_region", "label_ru": "Селлярная область", "type": "select", "options": ["Без особенностей", "Изменена"], "default": "Без особенностей"},
                ],
                "description_template": "МР-исследование головного мозга выполнено в стандартных импульсных последовательностях. Срединные структуры не смещены. Дифференциация серого и белого вещества сохранена. Очаговых изменений МР-сигнала в веществе мозга не выявлено. Желудочковая система не расширена. Субарахноидальные пространства без выраженной асимметрии. Селлярная область без особенностей.",
                "conclusion_template": "МР-признаков очаговой патологии головного мозга не выявлено.",
            },
            {
                "name_ru": "Рентгенография ОГК — норма",
                "name_kz": "Кеуде қуысы рентгенографиясы — норма",
                "modality": "CR",
                "body_part": "Легкие",
                "service_id": services_by_code.get("A06.10.001").id if services_by_code.get("A06.10.001") else None,
                "fields_schema": [
                    {"field_key": "lung_fields", "label_ru": "Легочные поля", "type": "select", "options": ["Без очаговых и инфильтративных теней", "Инфильтрация", "Очаговые тени"], "default": "Без очаговых и инфильтративных теней"},
                    {"field_key": "roots", "label_ru": "Корни легких", "type": "select", "options": ["Структурны", "Уплотнены", "Расширены"], "default": "Структурны"},
                    {"field_key": "sinuses", "label_ru": "Плевральные синусы", "type": "select", "options": ["Свободны", "Спайки", "Выпот"], "default": "Свободны"},
                    {"field_key": "heart_shadow", "label_ru": "Тень сердца", "type": "select", "options": ["Не расширена", "Расширена"], "default": "Не расширена"},
                ],
                "description_template": "Легочные поля без очаговых и инфильтративных теней. Легочный рисунок не усилен. Корни легких структурны, не расширены. Купола диафрагмы четкие. Плевральные синусы свободны. Тень сердца не расширена.",
                "conclusion_template": "Рентгенологических признаков активной патологии органов грудной клетки не выявлено.",
            },
            {
                "name_ru": "УЗИ органов брюшной полости — базовый",
                "name_kz": "Іш қуысы ағзаларының УДЗ — базалық",
                "modality": "US",
                "body_part": "Брюшная полость",
                "service_id": services_by_code.get("A06.21.001").id if services_by_code.get("A06.21.001") else None,
                "fields_schema": [
                    {"field_key": "liver", "label_ru": "Печень", "type": "select", "options": ["Не увеличена", "Увеличена", "Диффузные изменения"], "default": "Не увеличена"},
                    {"field_key": "gallbladder", "label_ru": "Желчный пузырь", "type": "select", "options": ["Без особенностей", "Конкременты", "Деформация"], "default": "Без особенностей"},
                    {"field_key": "pancreas", "label_ru": "Поджелудочная железа", "type": "select", "options": ["Без особенностей", "Диффузные изменения"], "default": "Без особенностей"},
                    {"field_key": "free_fluid", "label_ru": "Свободная жидкость", "type": "select", "options": ["Не выявлена", "Выявлена"], "default": "Не выявлена"},
                ],
                "description_template": "Печень не увеличена, контуры ровные, эхоструктура однородная. Желчный пузырь обычной формы, стенка не утолщена, конкременты не визуализируются. Поджелудочная железа визуализируется, контуры ровные. Селезенка не увеличена. Свободная жидкость в брюшной полости не определяется.",
                "conclusion_template": "УЗ-признаков выраженной патологии органов брюшной полости не выявлено.",
            },
            {
                "name_ru": "МРТ поясничного отдела позвоночника — дегенеративные изменения",
                "name_kz": "Бел омыртқасының МРТ — дегенеративті өзгерістер",
                "modality": "MR",
                "body_part": "Поясничный отдел позвоночника",
                "service_id": services_by_code.get("A06.20.030").id if services_by_code.get("A06.20.030") else None,
                "fields_schema": [
                    {"field_key": "lordosis", "label_ru": "Поясничный лордоз", "type": "select", "options": ["Сохранён", "Сглажен", "Усилен"], "default": "Сохранён"},
                    {"field_key": "disc_dehydration", "label_ru": "Дегидратация дисков", "type": "select", "options": ["Нет", "Умеренная", "Выраженная"], "default": "Умеренная"},
                    {"field_key": "herniation_level", "label_ru": "Уровень протрузии/грыжи", "type": "text", "default": "L4-L5, L5-S1"},
                    {"field_key": "canal_stenosis", "label_ru": "Стеноз позвоночного канала", "type": "select", "options": ["Нет", "Умеренный", "Выраженный"], "default": "Нет"},
                    {"field_key": "root_compression", "label_ru": "Компрессия корешков", "type": "select", "options": ["Нет", "Справа", "Слева", "Двусторонняя"], "default": "Нет"},
                ],
                "description_template": "Поясничный лордоз сохранён. Высота тел позвонков сохранена, костно-деструктивных изменений не выявлено. Отмечаются признаки дегенеративно-дистрофических изменений межпозвонковых дисков с умеренным снижением интенсивности МР-сигнала на T2. На уровнях L4-L5, L5-S1 определяются циркулярные протрузии дисков без значимой компрессии дурального мешка. Позвоночный канал обычной ширины. Конус спинного мозга без особенностей.",
                "conclusion_template": "МР-картина умеренных дегенеративно-дистрофических изменений поясничного отдела позвоночника. Протрузии дисков L4-L5, L5-S1 без значимого стеноза позвоночного канала.",
            },
            {
                "name_ru": "МРТ коленного сустава — мениск",
                "name_kz": "Тізе буынының МРТ — мениск",
                "modality": "MR",
                "body_part": "Коленный сустав",
                "service_id": services_by_code.get("A06.20.040").id if services_by_code.get("A06.20.040") else None,
                "fields_schema": [
                    {"field_key": "medial_meniscus", "label_ru": "Медиальный мениск", "type": "select", "options": ["Без разрыва", "Дегенеративные изменения", "Разрыв заднего рога", "Разрыв тела"], "default": "Дегенеративные изменения"},
                    {"field_key": "lateral_meniscus", "label_ru": "Латеральный мениск", "type": "select", "options": ["Без особенностей", "Дегенеративные изменения", "Разрыв"], "default": "Без особенностей"},
                    {"field_key": "acl", "label_ru": "Передняя крестообразная связка", "type": "select", "options": ["Интактна", "Частичное повреждение", "Разрыв"], "default": "Интактна"},
                    {"field_key": "cartilage", "label_ru": "Суставной хрящ", "type": "select", "options": ["Сохранён", "Хондромаляция I-II", "Хондромаляция III-IV"], "default": "Сохранён"},
                    {"field_key": "effusion", "label_ru": "Выпот", "type": "select", "options": ["Нет", "Небольшой", "Умеренный"], "default": "Небольшой"},
                ],
                "description_template": "Конгруэнтность суставных поверхностей сохранена. Костно-травматических изменений не выявлено. В медиальном мениске определяются дегенеративные изменения без убедительных признаков дислоцированного фрагмента. Латеральный мениск без признаков разрыва. Передняя и задняя крестообразные связки прослеживаются, целостность сохранена. Коллатеральные связки без особенностей. В полости сустава небольшое количество жидкости.",
                "conclusion_template": "МР-признаки дегенеративных изменений медиального мениска. Небольшой синовит. Данных за полный разрыв крестообразных связок не получено.",
            },
            {
                "name_ru": "Маммография — BI-RADS 2",
                "name_kz": "Маммография — BI-RADS 2",
                "modality": "MG",
                "body_part": "Молочные железы",
                "service_id": services_by_code.get("A06.30.001").id if services_by_code.get("A06.30.001") else None,
                "fields_schema": [
                    {"field_key": "density", "label_ru": "Плотность ткани", "type": "select", "options": ["ACR A", "ACR B", "ACR C", "ACR D"], "default": "ACR B"},
                    {"field_key": "masses", "label_ru": "Объёмные образования", "type": "select", "options": ["Не выявлены", "Доброкачественные", "Подозрительные"], "default": "Не выявлены"},
                    {"field_key": "calcifications", "label_ru": "Кальцинаты", "type": "select", "options": ["Нет", "Доброкачественные", "Подозрительные"], "default": "Доброкачественные"},
                    {"field_key": "birads", "label_ru": "BI-RADS", "type": "select", "options": ["1", "2", "3", "4", "5"], "default": "2"},
                ],
                "description_template": "Молочные железы представлены фиброзно-жировой тканью. Архитектоника ткани не нарушена. Узловых образований с подозрительными рентгенологическими признаками не выявлено. Определяются единичные доброкачественные кальцинаты. Кожа и сосково-ареолярные комплексы без особенностей. Подмышечные лимфатические узлы без патологических изменений.",
                "conclusion_template": "Доброкачественные изменения молочных желез. BI-RADS 2. Плановый скрининговый контроль.",
            },
        ]

        created_templates = 0
        for tmpl_data in templates_data:
            existing = await session.execute(
                select(ProtocolTemplate).where(ProtocolTemplate.name_ru == tmpl_data["name_ru"])
            )
            if existing.scalar_one_or_none():
                continue
            session.add(ProtocolTemplate(**tmpl_data))
            created_templates += 1

        await session.flush()
        if created_templates:
            print(f"Loaded {created_templates} protocol templates")
        else:
            print("Protocol templates already loaded, skipping")
        
        await session.commit()
        print("\nSeed completed successfully!")
        print("Default admin: login=admin, password=admin123")


if __name__ == "__main__":
    asyncio.run(seed())
