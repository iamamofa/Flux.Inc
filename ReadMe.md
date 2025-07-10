# **Facility Logistics Utilization Xpert** - Genomics and Bioinformatics Core Facility Lab

## Inventory System

Welcome to the **Facility Logistics Utilization Xpert** (Flux), a comprehensive inventory management solution developed for the **Genomics and Bioinformatics Core Facility Lab**. Flux is designed to optimize inventory operations, ensuring seamless tracking, organization, and accessibility of lab materials, equipment, and consumables. This Django-based system offers a robust and intuitive platform that supports the day-to-day logistics of managing products, stock levels, and reporting across various scientific endeavors, particularly in genomics and bioinformatics.

Whether you're managing reagents, consumables, or lab equipment, Flux provides the tools necessary to maintain accurate stock levels, streamline workflow, and make data-driven decisions. It is tailored to enhance operational efficiency, minimize errors, and improve the overall management of resources in both the Noguchi facility and beyond.

---

## Key Features

Flux integrates a wide range of features designed to provide flexibility, control, and insight into your inventory management process. Below are the core functionalities that make Flux a powerful tool for laboratory operations:

- **Product Management**  
  Easily manage inventory items. Users can add, edit, and delete products with detailed information like name, description, quantity, supplier, and expiration date.

- **Stock Tracking**  
  Real-time tracking of product stock levels. Avoid shortages or overstock with configurable low-stock alerts.

- **User Authentication**  
  Role-based access control.  
  - **Admin**: Full access, user and product management, reporting.  
  - **Staff**: Access limited to assigned responsibilities.

- **Reports**  
  Generate comprehensive inventory reports (graphical and tabular) on usage and stock levels. Export in CSV or PDF.

- **Search and Filtering**  
  Powerful search and filtering options by product name, category, or quantity.

- **Barcode Scanning Support**  
  Integrated barcode scanning for fast product updates and accurate stock handling.

---

## Getting Started

### Prerequisites

Ensure the following tools are installed before proceeding:

- **Python 3.6+**: [https://www.python.org/downloads/](https://www.python.org/downloads/)
- **Git**: [https://git-scm.com/](https://git-scm.com/)
- **Virtual Environment**: Recommended to isolate dependencies.

---

### Installation Instructions

#### Step 1: Clone the Repository

```bash
git clone https://github.com/iamamofa/flux.git
cd flux
```

#### Step 2: Create a Virtual Environment

```bash
python -m venv venv
```

#### Step 3: Activate the Virtual Environment

- **Linux/macOS**:

  ```bash
  source venv/bin/activate
  ```

- **Windows**:

  ```bash
  venv\Scripts\activate
  ```

#### Step 4: Install Dependencies

```bash
pip install -r requirements.txt
```

#### Step 5: Apply Migrations

```bash
python manage.py migrate
```

#### Step 6: Create a Superuser

```bash
python manage.py createsuperuser
```

Enter a username, email, and password as prompted.

#### Step 7: Run the Development Server

```bash
python manage.py runserver
```

The development server will start at:

- [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- Admin Panel: [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)

---

## Additional Configuration and Customization

Flux is flexible and customizable to suit your lab's unique requirements.

### Some additional configurations include:

- **Email Notifications**  
  Set up email in `settings.py` to receive alerts for low-stock items or important events.

- **Custom Reports**  
  Extend the reporting module for more detailed lab-specific analytics.

- **UI Modifications or Integrations**  
  Modify templates or connect with other systems as needed.

---

## Conclusion

The **Facility Logistics Utilization Xpert (Flux)** is a powerful inventory management system tailored for the logistics needs of genomics and bioinformatics labs. With features like real-time stock tracking, barcode support, role-based access, and detailed reporting, Flux helps your lab stay organized, minimize errors, and focus on scientific innovation.

Whether at Noguchi or another facility, Flux ensures your inventory is reliable, trackable, and ready to support high-impact research.

---
