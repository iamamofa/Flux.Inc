from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from inventory.models import Project, Consumable, Reagent, Equipment, Sample, Shelf, Box
from faker import Faker
import random

fake = Faker()

class Command(BaseCommand):
    help = 'Populates the database with dummy data'

    def handle(self, *args, **kwargs):
        # Create Users
        for _ in range(5):
            User.objects.create_user(
                username=fake.user_name(),
                email=fake.email(),
                password='testpass123'
            )

        users = User.objects.all()

        # Create Projects
        for _ in range(3):
            Project.objects.create(
                name=fake.unique.company(),
                project_manager=random.choice(users)
            )

        projects = Project.objects.all()

        # Create Consumables
        for _ in range(20):
            Consumable.objects.create(
                project=random.choice(projects),
                name=fake.word(),
                product_code=fake.unique.bothify('??-###'),
                pack_size=random.randint(1, 100),
                pack_size_rem=random.randint(1, 100),
                quantity=random.randint(1, 1000),
                expiry_date=fake.date_between(start_date='today', end_date='+2y'),
                storage_location=fake.word(),
                threshold_value=random.randint(5, 20)
            )

        # Create Reagents
        for _ in range(15):
            Reagent.objects.create(
                project=random.choice(projects),
                name=fake.word(),
                product_code=fake.unique.bothify('??-###'),
                pack_size=random.randint(1, 100),
                pack_size_rem=random.randint(1, 100),
                quantity=random.randint(1, 1000),
                expiry_date=fake.date_between(start_date='today', end_date='+3y'),
                storage_location=fake.word(),
                threshold_value=random.randint(5, 20)
            )

        # Create Equipment
        for _ in range(10):
            Equipment.objects.create(
                project=random.choice(projects),
                name=fake.word(),
                equip_id=fake.uuid4(),
                serial_num=fake.uuid4(),
                quantity=random.randint(1, 10),
                status=random.choice(['Active', 'Inactive', 'Under Maintenance']),
                service_contract_start=fake.date_this_decade(),
                service_contract_end=fake.date_between(start_date='+1y', end_date='+3y'),
                donated_by=fake.company(),
                storage_location=fake.word()
            )

        # Create Sample Storage (Shelf & Box)
        for _ in range(5):
            shelf = Shelf.objects.create(
                name=fake.word(),
                description=fake.sentence(),
                project=random.choice(projects)
            )
            for _ in range(2):
                Box.objects.create(
                    name=fake.word(),
                    description=fake.sentence(),
                    shelf=shelf,
                    project=shelf.project
                )

        shelves = Shelf.objects.all()
        boxes = Box.objects.all()

        # Create Samples
        for _ in range(25):
            Sample.objects.create(
                project=random.choice(projects),
                shelf=random.choice(shelves),
                box=random.choice(boxes),
                sample_id=fake.unique.uuid4(),
                sample_type=random.choice(['Blood', 'Tissue', 'Urine']),
                description=fake.text(max_nb_chars=50),
                country=fake.country(),
                volume=random.randint(1, 100),
                well_id=fake.bothify('A##'),
                storage_location=fake.word(),
                threshold_value=random.randint(5, 10)
            )

        self.stdout.write(self.style.SUCCESS("🎉 Dummy data successfully populated!"))
