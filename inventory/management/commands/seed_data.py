import os
import django
# Configure Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory_system.settings')
django.setup()

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from inventory.models import (
    Project, Consumable, Reagent, Equipment, Sample, Shelf, Box,
    UserProfile, Rooms, Storages, Rack, Log, MSDSSection,
    # Assuming the names are correct based on models.py
    BaseInventoryItem,
    Sample_Locations,
)
from faker import Faker
import random
from datetime import timedelta
from django.utils import timezone
import logging

fake = Faker()
# Set up a logger for seeding progress
seeder_logger = logging.getLogger('db_seeder')
seeder_logger.setLevel(logging.INFO)
# Prevent propagation to avoid duplicate output if running in a shell
seeder_logger.propagate = False 
if not seeder_logger.handlers:
    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(levelname)s: %(message)s')
    ch.setFormatter(formatter)
    seeder_logger.addHandler(ch)


# --- Realistic Data Pools ---

DEPARTMENTS = [
    "Virology", "Bacteriology", "Parasitology", "Immunology", 
    "Biochemistry", "Molecular Biology", "Clinical Trials", 
    "Data Science", "Administration"
]

PROJECT_THEMES = [
    "Viral Pathogenesis in Africa", "Drug Resistance Mechanisms", 
    "Malaria Vaccine Efficacy", "HIV/TB Co-infection", 
    "Host-Pathogen Interactions", "AI-driven Diagnostics",
    "Oncology Biomarker Discovery", "Zoonotic Disease Surveillance"
]

CONSUMABLES = [
    "Gloves (Nitrile M)", "Pipette Tips (1000µL)", "Microcentrifuge Tubes (1.5mL)", 
    "PCR Plates (96-well)", "Cell Culture Dishes (100mm)", "Cryovials (2.0mL)",
    "Sterile Water (HPLC Grade)", "Ethanol (99%)", "Parafilm M"
]

REAGENTS = [
    "PBS 10X Solution", "Taq DNA Polymerase", "FBS (Fetal Bovine Serum)", 
    "Trypsin-EDTA", "DNase/RNase Free Water", "Gel Staining Solution",
    "DAPI Stain", "RNA Extraction Kit (50 Preps)"
]

EQUIPMENT = [
    "PCR Thermal Cycler (Model A)", "High-Speed Centrifuge (Model B)", 
    "Inverted Microscope (Fluorescence)", "Biosafety Cabinet (Class II)",
    "Ultra-Low Freezer (-80°C)", "Analytical Balance", "pH Meter"
]

SAMPLE_TYPES = [
    "Whole Blood", "Extracted DNA", "RNA Lysate", "Plasma", 
    "Urine", "Fixed Tissue Block", "Cell Line Suspension"
]

STORAGE_LOCATIONS_MAP = {
    'Ambient': ['Room Temp Shelves'],
    'Refrigerated': ['4°C Fridge/Shelf 1', '4°C Cold Room/Rack A'],
    'Freezer': ['-20°C Freezer/Shelf 2', '-80°C Freezer/Rack B', 'LN2 Tank/Rack C']
}

# --- Utility Functions ---

def get_random_storage_location(temp_key):
    """Returns a storage location string based on temperature category."""
    locations = STORAGE_LOCATIONS_MAP.get(temp_key, [])
    if not locations:
        return ""
    # Extract the main location name from the string, e.g., '4°C Fridge/Shelf 1' -> '4°C Fridge'
    return random.choice(locations).split('/')[0]

def get_random_cold_storage_type(temp_key):
    """Returns a cold storage identifier."""
    if temp_key == 'Freezer':
        return random.choice(['-20C', '-80C', 'LN2'])
    elif temp_key == 'Refrigerated':
        return '4C'
    return 'NA'

# --- Custom Command Class ---

class Command(BaseCommand):
    help = 'Populates the database with a realistic hierarchical lab inventory structure.'

    def handle(self, *args, **kwargs):
        seeder_logger.info("Starting comprehensive database seeding...")
        
        # Clear existing non-essential data for a clean run
        self.clear_existing_data()
        
        # --- 1. USERS & PROFILES ---
        seeder_logger.info("1. Creating Users and UserProfiles...")
        self.create_users()
        
        # --- 2. PROJECTS ---
        seeder_logger.info("2. Creating Projects and assigning Management/Roles...")
        self.create_projects()

        # --- 3. INFRASTRUCTURE (Rooms, Storages, Shelves, Racks, Boxes) ---
        seeder_logger.info("3. Creating Storage Infrastructure...")
        self.create_infrastructure()
        
        # --- 4. INVENTORY ITEMS (Consumables, Reagents, Equipment, Samples) ---
        seeder_logger.info("4. Populating Inventory (Consumables, Reagents, Equipment, Samples)...")
        self.populate_inventory()
        
        # --- 5. LOGS & MSDS Sections (Utility/Audit Data) ---
        seeder_logger.info("5. Creating Audit Logs and MSDS Configuration...")
        self.create_utility_data()
        
        seeder_logger.info(self.style.SUCCESS("✅ Database seeding complete!"))
        self.print_summary()

    def clear_existing_data(self):
        """A simple way to clear data for models we're seeding."""
        seeder_logger.warning("Clearing existing data for Project, UserProfile, and Inventory models...")
    
        # --- Critical Fix: Ensure old UserProfiles are gone before touching Users ---
        # This prevents the UNIQUE constraint error on UserProfile.user_id
        UserProfile.objects.all().delete()
    
        # --- Delete Seeded Users to prevent conflicts in the next run ---
        # This list should contain the usernames of all users created in create_users()
        seeded_usernames = [
            'lab_admin', 'pi_director', 'tech_manager', 'guest_user'
        ] + [f"pi_{i+1}" for i in range(4)] \
        + [f"editor_{i+1}" for i in range(6)] \
        + [f"member_{i+1}" for i in range(10)]
      
        User.objects.filter(username__in=seeded_usernames).delete()
    
        # --- Clear all other seeded models ---
        Project.objects.all().delete()
        Consumable.objects.all().delete()
        Reagent.objects.all().delete()
        Equipment.objects.all().delete()
        Sample.objects.all().delete()
        Shelf.objects.all().delete()
        Box.objects.all().delete()
        Rack.objects.all().delete()
        Rooms.objects.all().delete()
        Storages.objects.all().delete()
        Log.objects.all().delete()
        MSDSSection.objects.all().delete()
        
    def create_users(self):
        """
        Creates a variety of users with different levels/roles.
        Relies on the post_save signal in models.py to create the UserProfile,
        and then updates the profile fields.
        """
    
        # 1. High-level PI/Admin
        # Use get_or_create for robustness
        admin_user, created = User.objects.get_or_create(
            username='lab_admin',
            defaults={
                'email': 'admin@noguchi.ug.edu.gh',
                'first_name': 'Head',
                'last_name': 'Admin',
                'is_staff': True,
                'is_superuser': True
            }
        )
        if created:
            admin_user.set_password('password123')
            admin_user.save()
    
        # Update the profile fields (signal ensures profile exists)
        admin_user.profile.department = 'Administration'
        admin_user.profile.phone_number = '555-000-0001'
        admin_user.profile.save() # Use save() to trigger an update, or use .update()

    
        pi_users = []
        # 2. Principal Investigators (Project Managers)
        for i in range(4):
            username = f"pi_{i+1}"
            user = User.objects.create_user(
                username=username,
                email=f"{username}@noguchi.ug.edu.gh",
                password='password123',
                first_name=fake.first_name(),
                last_name=fake.last_name(),
            )
            # FIX: Instead of calling UserProfile.objects.create(), update the existing profile
            user.profile.department = random.choice(DEPARTMENTS)
            user.profile.phone_number = fake.phone_number()
            user.profile.save()

            pi_users.append(user)

        editor_users = []
        # 3. Senior Researchers (Editors)
        for i in range(6):
            username = f"editor_{i+1}"
            user = User.objects.create_user(
                username=username,
                email=f"{username}@noguchi.ug.edu.gh",
                password='password123',
                first_name=fake.first_name(),
                last_name=fake.last_name(),
            )
            # FIX: Instead of calling UserProfile.objects.create(), update the existing profile
            user.profile.department = random.choice(DEPARTMENTS)
            user.profile.phone_number = fake.phone_number()
            user.profile.save()

            editor_users.append(user)

        member_users = []
        # 4. Research Assistants/Technicians (Members)
        for i in range(10):
            username = f"member_{i+1}"
            user = User.objects.create_user(
                username=username,
                email=f"{username}@noguchi.ug.edu.gh",
                password='password123',
                first_name=fake.first_name(),
                last_name=fake.last_name(),
            )
            # FIX: Instead of calling UserProfile.objects.create(), update the existing profile
            user.profile.department = random.choice(DEPARTMENTS)
            user.profile.phone_number = fake.phone_number()
            user.profile.save()
        
            member_users.append(user)

        self.users = {'pi': pi_users, 'editor': editor_users, 'member': member_users, 'all': pi_users + editor_users + member_users}

    def create_projects(self):
        """Creates projects and assigns managers, editors, and members."""
        projects = []
        pi_index = 0
        for i, theme in enumerate(PROJECT_THEMES):
            if pi_index >= len(self.users['pi']):
                pi_index = 0
                
            project_manager = self.users['pi'][pi_index]
            project_name = f"{theme} ({project_manager.last_name})"
            
            project, created = Project.objects.get_or_create(
                name=project_name,
                defaults={'project_manager': project_manager, 'is_active': random.choice([True, True, True, False])}
            )
            projects.append(project)
            pi_index += 1

            # Assign roles
            other_users = [u for u in self.users['all'] if u != project_manager]
            
            # Editors: Assign 1-2 senior researchers/other PIs
            editors_pool = self.users['editor'] + [u for u in self.users['pi'] if u != project_manager]
            editors = random.sample(editors_pool, k=min(2, len(editors_pool)))
            project.project_editors.set(editors)

            # Members: Assign 2-5 research assistants
            members = random.sample(self.users['member'], k=random.randint(2, 5))
            project.project_members.set(members)
            
            # Update UserProfile managed_projects (optional, but good practice if UserProfile is the primary link)
            UserProfile.objects.get(user=project_manager).managed_projects.add(project)
            for user in editors + members:
                 # Check if the user has a profile (they should)
                try:
                    UserProfile.objects.get(user=user).managed_projects.add(project)
                except UserProfile.DoesNotExist:
                    pass # Handled by post_save signal, but ensures all are added here

        self.projects = projects

    def create_infrastructure(self):
        """Creates physical storage locations."""
        seeder_logger.info("3.1 Creating Rooms and Storages...")
        
        # Create a few rooms
        room_a = Rooms.objects.create(room_name="Lab 101 - Molecular", building="Main Research Block")
        room_b = Rooms.objects.create(room_name="Lab 102 - Cell Culture", building="Main Research Block")
        
        # Create storages within rooms
        storage_fridge = Storages.objects.create(room_id=room_a, storage_name="Cold Room Unit 1", storage_type="Cold Room", temperature=4, temperature_unit='C')
        storage_freezer = Storages.objects.create(room_id=room_a, storage_name="Revco ULT Freezer", storage_type="Ultra Low Freezer", temperature=-80, temperature_unit='C')
        storage_cabinet = Storages.objects.create(
            room_id=room_b, 
            storage_name="Biosafety Cabinet A", 
            storage_type="BSC", 
            temperature=25, 
            temperature_unit='C', 
            notes="Only for sterile work."
        )
        
        self.storages = [storage_fridge, storage_freezer, storage_cabinet]
        
        seeder_logger.info("3.2 Creating Shelves, Racks, and Boxes...")
        
        self.shelves = []
        self.racks = []
        self.boxes = []
        
        # Assign shelves/racks/boxes to different projects
        for project in random.sample(self.projects, k=min(4, len(self.projects))):
            # Create 2 shelves in the cold room
            for i in range(1, 3):
                shelf = Shelf.objects.create(
                    storage=storage_fridge, 
                    project=project, 
                    shelf_label=f"CR-Shelf {i} - {project.name[:5]}", 
                    capacity=100
                )
                self.shelves.append(shelf)

            # Create 1 rack in the freezer
            rack = Rack.objects.create(
                shelf=random.choice(self.shelves), # Racks must be on a shelf, pick a random one
                project=project, 
                project_manager=project.project_manager,
                rack_label=f"ULT-Rack {project.name[:5]}", 
                capacity=50
            )
            self.racks.append(rack)
            
            # Create boxes in the rack
            for j in range(1, 4):
                box = Box.objects.create(
                    rack=rack, 
                    project=project, 
                    box_label=f"Box {j}", 
                    row_count=8, 
                    column_count=12
                )
                self.boxes.append(box)
                
        # Also create a few unassigned infrastructure pieces
        Shelf.objects.create(storage=storage_cabinet, project=self.projects[0], shelf_label="Bench Shelf 1")

    def populate_inventory(self):
        """Populates inventory items linked to projects and storage."""
        
        # --- CONSUMABLES ---
        seeder_logger.info("4.1 Creating Consumables...")
        for name in CONSUMABLES:
            project = random.choice(self.projects)
            pack_count = random.randint(1, 15)
            items_per_pack = random.choice([50, 100, 500])
            cold_storage_key = random.choice(['Ambient', 'Refrigerated'])
            
            Consumable.objects.create(
                project=project,
                name=name,
                product_code=fake.unique.bothify('CON-#####-##'),
                items_per_pack=items_per_pack,
                items_left_in_pack=random.randint(1, items_per_pack),
                pack_count=pack_count,
                expiry_date=fake.date_between(start_date='+6m', end_date='+5y'),
                storage_location=get_random_storage_location(cold_storage_key),
                cold_storage=get_random_cold_storage_type(cold_storage_key),
                oem_temperature=random.choice([25, 4, 4, 4, 4, 25, 25, 25]),
                vendor=fake.company(),
                threshold_value=max(1, pack_count // 3),
            )
            
        # --- REAGENTS ---
        seeder_logger.info("4.2 Creating Reagents...")
        for name in REAGENTS:
            project = random.choice(self.projects)
            pack_count = random.randint(1, 8)
            items_per_pack = random.choice([1, 5, 10, 20])
            cold_storage_key = random.choice(['Refrigerated', 'Freezer', 'Freezer'])
            
            Reagent.objects.create(
                project=project,
                name=name,
                product_code=fake.unique.bothify('REA-#####-KIT'),
                items_per_pack=items_per_pack,
                items_left_in_pack=random.randint(1, items_per_pack),
                pack_count=pack_count,
                expiry_date=fake.date_between(start_date='-3m', end_date='+2y'), # Include some expired ones
                storage_location=get_random_storage_location(cold_storage_key),
                cold_storage=get_random_cold_storage_type(cold_storage_key),
                oem_temperature=random.choice([-80, -20, 4, 4, 4]),
                vendor=fake.company(),
                threshold_value=max(1, pack_count // 2),
                country_of_origin=fake.country_code(),
                hazard_level=random.randint(0, 4)
            )

        # --- EQUIPMENT ---
        seeder_logger.info("4.3 Creating Equipment...")
        for name in EQUIPMENT:
            project = random.choice(self.projects)
            status = random.choice(['operational', 'operational', 'operational', 'maintenance', 'faulty'])
            Equipment.objects.create(
                project=project,
                name=name,
                equip_id=fake.unique.bothify('EQ-##-###'),
                serial_num=fake.unique.bothify('SN-#########'),
                status=status,
                service_contract_start=fake.date_between(start_date='-5y', end_date='-1y'),
                service_contract_end=fake.date_between(start_date='today', end_date='+3y'),
                date_installed=fake.date_between(start_date='-10y', end_date='-2y'),
                source=random.choice(["Purchased", "Grant", "Donation"]),
                operating_temperature=random.choice([4, -20, -80, 37, 25, None]),
                storage_location=f"Room {random.randint(101, 105)}"
            )

        # --- SAMPLES ---
        seeder_logger.info("4.4 Creating Samples and Locations...")
        
        # Only use boxes we created that are linked to a project
        boxes_for_samples = [box for box in self.boxes if box.project]
        
        for _ in range(100):
            if not boxes_for_samples:
                break
                
            selected_box = random.choice(boxes_for_samples)
            sample_type = random.choice(SAMPLE_TYPES)
            volume = fake.pydecimal(left_digits=2, right_digits=2, positive=True)
            
            sample = Sample.objects.create(
                project=selected_box.project,
                sample_id=fake.unique.bothify('SAM-####-##'),
                sample_type=sample_type,
                country=fake.country(),
                volume=volume,
                volume_unit=random.choice(['mL', 'µL']),
                collection_date=fake.date_between(start_date='-5y', end_date='today'),
                notes=f"{sample_type} collected for {random.choice(['sequencing', 'culture', 'storage'])}",
                threshold_value=random.randint(1, 5)
            )

            # Create Sample_Locations entry
            row = random.randint(1, selected_box.row_count)
            col = random.randint(1, selected_box.column_count)
            well_id = f"{chr(64 + row)}{col:02d}"

            Sample_Locations.objects.create(
                sample=sample,
                box=selected_box,
                well_id=well_id,
                moved_in_at=sample.collection_date
            )

    def create_utility_data(self):
        """Creates data for Log and MSDSSection models."""
        
        # --- LOGS ---
        seeder_logger.info("5.1 Creating Audit Log entries...")
        random_project = random.choice(self.projects)
        random_user = random.choice(self.users['all'])
        
        # Create a few typical log entries
        Log.objects.create(
            project=random_project,
            user=random_user,
            action="Consumable Added",
            details={"item_name": "Gloves (M)", "pack_count": 5, "location": "CR-Shelf 1"},
            timestamp=timezone.now() - timedelta(hours=5)
        )
        Log.objects.create(
            project=random_project,
            user=random_user,
            action="Reagent Consumed",
            details={"item_name": "Taq DNA Polymerase", "packs_removed": 1, "reason": "PCR experiment"},
            timestamp=timezone.now() - timedelta(hours=2)
        )
        
        # --- MSDS Sections ---
        seeder_logger.info("5.2 Creating default MSDS Sections...")
        sections_data = [
            ("Identification", True, "product identifier,recommended use,supplier details", 1),
            ("Hazard(s) Identification", True, "classification,hazard statements,precautionary statements", 2),
            ("Composition/Information on Ingredients", True, "chemical name,CAS number,concentration", 3),
            ("First-Aid Measures", False, "eye contact,skin contact,inhalation,ingestion", 4),
            ("Fire-Fighting Measures", False, "extinguishing media,hazardous combustion products", 5),
        ]
        
        for name, required, keywords, order in sections_data:
            MSDSSection.objects.create(
                name=name,
                required=required,
                keywords=keywords,
                order=order
            )
    def print_summary(self):
        """Prints a summary of the seeded data."""
    
        # Calculate total inventory items by summing the counts of the concrete models
        total_inventory = (
            Consumable.objects.count() +
            Reagent.objects.count() +
            Equipment.objects.count() +
            Sample.objects.count()
        )

        self.stdout.write("\n--- SEEDING SUMMARY ---")
        self.stdout.write(f"Total Users: {User.objects.count()}")
        self.stdout.write(f"Total Projects: {Project.objects.count()}")
        self.stdout.write(f"Total Storage Units (Rooms/Storages): {Rooms.objects.count()}/{Storages.objects.count()}")
    
        # Use the calculated total
        self.stdout.write(f"Total Inventory Items: {total_inventory}")
    
        # The individual counts below are now correct and informative:
        self.stdout.write(f"  - Consumables: {Consumable.objects.count()}")
        self.stdout.write(f"  - Reagents: {Reagent.objects.count()}")
        self.stdout.write(f"  - Equipment: {Equipment.objects.count()}")
        self.stdout.write(f"  - Samples: {Sample.objects.count()}")
        self.stdout.write(f"Total Sample Locations: {Sample_Locations.objects.count()}")
        self.stdout.write("-----------------------\n")
