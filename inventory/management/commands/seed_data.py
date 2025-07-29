import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory_system.settings')
django.setup()

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from inventory.models import Project, Consumable, Reagent, Equipment, Sample, Shelf, Box, UserProfile
from faker import Faker
import random

fake = Faker()

# Biomedical-specific data lists
CONSUMABLES = [
    "Gloves", "Pipette Tips", "Microcentrifuge Tubes", "PCR Tubes", 
    "Petri Dishes", "Cell Culture Plates", "Syringes", "Centrifuge Tubes",
    "Cryovials", "Filter Tips", "Microscope Slides", "Coverslips",
    "Parafilm", "Sterile Swabs", "Gauze Pads", "Alcohol Wipes",
    "Biohazard Bags", "Sharps Containers", "Tube Racks", "Sample Bags"
]

REAGENTS = [
    "PBS Buffer", "Tris Buffer", "EDTA", "SDS", "Agarose", 
    "Ethidium Bromide", "SYBR Green", "TAE Buffer", "TBE Buffer",
    "DNase I", "RNase A", "Proteinase K", "Restriction Enzymes",
    "PCR Master Mix", "dNTPs", "Primers", "Loading Dye",
    "Antibiotics", "Antifungal", "Trypsin", "FBS"
]

EQUIPMENT = [
    "Microcentrifuge", "PCR Machine", "Gel Doc System", "Electrophoresis Chamber",
    "Vortex Mixer", "Thermal Cycler", "Incubator", "Biosafety Cabinet",
    "Autoclave", "Microscope", "Spectrophotometer", "Centrifuge",
    "Water Bath", "Magnetic Stirrer", "pH Meter", "Balance",
    "Freezer (-20°C)", "Freezer (-80°C)", "Liquid Nitrogen Tank", "CO2 Incubator"
]

SAMPLE_TYPES = [
    "Whole Blood", "Plasma", "Serum", "Urine", "Saliva",
    "Tissue Biopsy", "Bone Marrow", "CSF", "Stool", "Sputum"
]

COUNTRIES = [
    "USA", "UK", "Germany", "France", "Japan",
    "China", "Brazil", "South Africa", "Australia", "Canada"
]


class Command(BaseCommand):
    help = 'Populates the database with realistic biomedical inventory data'

    def handle(self, *args, **kwargs):
        self.stdout.write("Creating biomedical inventory data...")

        # Create 5 Users with UserProfiles
        if User.objects.count() < 5:
            self.stdout.write("creating initial users...")
            for i in range(5):
                user_num = User.objects.count() + 1
                user = User.objects.create_user(
                    username=f"researcher_{i+1}",
                    email=f"researcher_{i+1}@noguchi.ug.edu.gh",
                    password='biomed123',
                    first_name=fake.first_name(),
                    last_name=fake.last_name()
                )
                UserProfile.objects.create(user=user)
                self.stdout.write(f"Created user: researcher_{user_num}")

        for user in User.objects.all():
            UserProfile.objects.get_or_create(user=user)

        # Create 10 Projects
        project_names = [
            "Genomics Initiative", "Proteomics Study", "Cancer Biomarkers",
            "Infectious Diseases", "Stem Cell Research", "Neurobiology",
            "Immunotherapy", "Vaccine Development", "Metabolic Disorders",
            "Precision Medicine"
        ]

        for name in project_names:
            # Use get_or_create to avoid duplicates
            project, created = Project.objects.get_or_create(
                name=name,
                defaults={
                    'project_manager': random.choice(User.objects.all())
                }
            )
            if created:
                self.stdout.write(f"Created project: {name}")
            else:
                self.stdout.write(f"Project already exists: {name}")

        # 4. Add team members to projects - SAFE VERSION
        all_users = list(User.objects.all())
        min_users = min(2, len(all_users))  # Ensure we don't request more than exists
        max_users = min(4, len(all_users))  # Same here

        for project in Project.objects.all():
            # Get random number of users between min and max (adjusted to user count)
            num_members = random.randint(min_users, max_users)
            members = random.sample(all_users, num_members)

            for user in members:
                profile = UserProfile.objects.get(user=user)
                if user != project.project_manager:
                    if random.choice([True, False]):
                        project.project_editors.add(user)
                    else:
                        project.project_members.add(user)
                    profile.managed_projects.add(project)

        projects = Project.objects.all()

        # Create storage infrastructure (Shelves and Boxes)
        for project in projects:
            for i in range(3):  # 3 shelves per project
                shelf = Shelf.objects.create(
                    name=f"Shelf {i+1}",
                    description=f"Storage shelf {i+1} in {project.name} lab",
                    project=project
                )

                for j in range(5):  # 5 boxes per shelf
                    Box.objects.create(
                        name=f"Box {j+1}",
                        description=f"Storage box {j+1} on {shelf.name}",
                        shelf=shelf,
                        project=project
                    )

        shelves = Shelf.objects.all()
        boxes = Box.objects.all()

        # Create Consumables (80 items)
        for _ in range(80):
            pack_size = random.choice([10, 25, 50, 100, 200, 500, 1000])
            quantity = random.randint(1, 20)

            Consumable.objects.create(
                project=random.choice(projects),
                name=random.choice(CONSUMABLES),
                product_code=fake.unique.bothify('CON-#####'),
                pack_size=pack_size,
                pack_size_rem=random.randint(1, pack_size),
                quantity=quantity,
                expiry_date=fake.date_between(start_date='today', end_date='+3y'),
                storage_location=random.choice(["Room Temp", "4°C", "-20°C"]),
                threshold_value=max(1, quantity // 4)  # 25% of quantity as threshold
            )

        # Create Reagents (60 items)
        for _ in range(60):
            pack_size = random.choice([1, 5, 10, 25, 50, 100])
            quantity = random.randint(1, 10)

            Reagent.objects.create(
                project=random.choice(projects),
                name=random.choice(REAGENTS),
                product_code=fake.unique.bothify('REA-#####'),
                pack_size=pack_size,
                pack_size_rem=random.randint(1, pack_size),
                quantity=quantity,
                expiry_date=fake.date_between(start_date='today', end_date='+2y'),
                storage_location=random.choice(["4°C", "-20°C", "-80°C", "LN2"]),
                threshold_value=max(1, quantity // 3)  # 33% of quantity as threshold
            )

        # Create Equipment (30 items)
        for _ in range(30):
            status = random.choice(["Active", "Active", "Active", "In Maintenance", "Retired"])

            Equipment.objects.create(
                project=random.choice(projects),
                name=random.choice(EQUIPMENT),
                equip_id=fake.unique.bothify('EQ-#####'),
                serial_num=fake.unique.bothify('SN#####'),
                quantity=1,  # Most equipment is single items
                status=status,
                service_contract_start=fake.date_between(start_date='-2y', end_date='today'),
                service_contract_end=fake.date_between(start_date='today', end_date='+3y'),
                donated_by=random.choice(["", "NIH Grant", "Wellcome Trust", "HHMI", "Company Donation"]),
                storage_location=f"Lab {random.randint(1, 5)}"
            )

        # Create Samples (30 items)
        for _ in range(30):
            sample_type = random.choice(SAMPLE_TYPES)
            volume = random.choice([1, 2, 5, 10, 20, 50, 100])

            Sample.objects.create(
                project=random.choice(projects),
                shelf=random.choice(shelves),
                box=random.choice(boxes),
                sample_id=fake.unique.bothify('SAM-#####'),
                sample_type=sample_type,
                description=f"{sample_type} sample collected for {random.choice(['DNA', 'RNA', 'protein'])} analysis",
                country=random.choice(COUNTRIES),
                volume=volume,
                well_id=f"{random.choice(['A', 'B', 'C', 'D'])}{random.randint(1, 12)}",
                storage_location=random.choice(["-20°C", "-80°C", "LN2"]),
                threshold_value=max(1, volume // 2)  # 50% of volume as threshold
            )

        self.stdout.write(self.style.SUCCESS("✅ Successfully created biomedical inventory data with:"))
        self.stdout.write(f"  - {User.objects.count()} users")
        self.stdout.write(f"  - {Project.objects.count()} projects")
        self.stdout.write(f"  - {Consumable.objects.count()} consumables")
        self.stdout.write(f"  - {Reagent.objects.count()} reagents")
        self.stdout.write(f"  - {Equipment.objects.count()} equipment items")
        self.stdout.write(f"  - {Sample.objects.count()} samples")
