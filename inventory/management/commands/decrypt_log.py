from django.core.management.base import BaseCommand
from cryptography.fernet import Fernet


class Command(BaseCommand):
    help = 'Decrypt log files for admin review'

    def add_arguments(self, parser):
        parser.add_argument('--file', help='Encrypted log file path', required=True)

    def handle(self, *args, **options):
        # Require physical presence of at least 2 admins
        share1 = input("Admin 1 Key Part: ").strip()
        share2 = input("Admin 2 Key Part: ").strip()

        from binascii import unhexlify
        from Crypto.Protocol.SecretSharing import Shamir

        # Combine the shares for original key
        shares = [
                (1, unhexlify(share1)),
                (2, unhexlify(share2))
        ]
        key = Shamir.combine(shares)

        fernet = Fernet(key)

        with open(options['file'], 'rb') as f:
            for line in f:
                try:
                    decrypted = fernet.decrypt(line.strip()).decode('utf-8')
                    self.stdout.write(decrypted)
                except Exception as e:
                    self.stderr.write(f"Failed to decrypt line: {e}")
