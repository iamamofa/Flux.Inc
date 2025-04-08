# **Facility Logistics Utilization Xpert** - Genomics and Bioinformatics Core Facility Lab
## Inventory System

Welcome to the **Facility Logistics Utilization Xpert** (Flux), a comprehensive inventory management solution developed for the **Genomics and Bioinformatics Core Facility Lab**. Flux is designed to optimize inventory operations, ensuring seamless tracking, organization, and accessibility of lab materials, equipment, and consumables. This Django-based system offers a robust and intuitive platform that supports the day-to-day logistics of managing products, stock levels, and reporting across various scientific endeavors, particularly in genomics and bioinformatics.

Whether you're managing reagents, consumables, or lab equipment, Flux provides the tools necessary to maintain accurate stock levels, streamline workflow, and make data-driven decisions. It is tailored to enhance operational efficiency, minimize errors, and improve the overall management of resources in both the Noguchi facility and beyond.

## Key Features

Flux integrates a wide range of features designed to provide flexibility, control, and insight into your inventory management process. Below are the core functionalities that make Flux a powerful tool for laboratory operations:

- **Product Management:**
  - The system allows for easy management of inventory items. Users can quickly add, edit, and delete products, ensuring that the inventory is always up-to-date. Each product entry can include detailed information such as product name, description, quantity, supplier, and expiration dates, making it easier to manage lab supplies.

- **Stock Tracking:**
  - Flux provides real-time tracking of product stock levels. This ensures that lab managers can always know exactly how much of each product is available, helping to avoid shortages or overstock situations. Automatic alerts can be configured for low stock levels, allowing users to replenish items before they run out.

- **User Authentication:**
  - Secure access to the system is enforced through role-based authentication. Flux supports multiple user roles, including **Admin** and **Staff**. Admins have full access to all system functionalities, including managing users, products, and generating reports. Staff users are granted access based on their responsibilities, ensuring that sensitive data is protected while still allowing users to perform necessary tasks.

- **Reports:**
  - Generate detailed reports on inventory performance, sales data, and stock levels. These reports are essential for analyzing product usage, forecasting future stock needs, and making informed purchasing decisions. Flux offers both graphical and tabular reports, and these can be exported in various formats, such as CSV or PDF, for further analysis or record-keeping.

- **Search and Filtering:**
  - The system includes powerful search and filter tools, allowing users to quickly find products based on specific attributes like name, category, or quantity. This feature significantly reduces the time spent manually searching through large inventories and helps maintain an organized workflow.

- **Barcode Scanning Support:**
  - For even more efficiency, Flux integrates barcode scanning capabilities. This allows users to quickly scan products for addition, deletion, or stock level updates, reducing the potential for human error and speeding up the inventory management process.

## Getting Started

Setting up **Flux** is easy and quick. Below are the instructions to help you get started, whether you are a lab manager looking to implement the system or a developer setting up the project for local testing and customization.

### Prerequisites

Before you begin the installation process, make sure you have the following software installed:

- **Python**: Flux is built using the Django framework, which requires Python. You can download and install Python from [here](https://www.python.org/downloads/). Make sure you have Python 3.6 or higher.

- **Git**: You’ll need Git to clone the repository. Git can be installed from [here](https://git-scm.com/).

- **Virtual Environment**: It's recommended to use a virtual environment to manage your dependencies in an isolated environment. This helps prevent conflicts with other Python projects on your machine.

### Installation Instructions

Follow the steps below to set up Flux on your local machine:

#### Step 1: Clone the Repository

To begin, clone the Flux repository from GitHub. This will give you access to the source code and allow you to run the project locally.

```bash
git clone https://github.com/iamamofa/flux.git
cd flux
```

## Step 2: Create a Virtual Environment
Once you've cloned the repository, create a virtual environment to handle the project’s dependencies:

```bash
python -m venv venv
```
```html
Step 3: Activate the Virtual Environment
Next, activate the virtual environment. The activation command varies depending on your operating system.
```

## For Linux/macOS:

bash

source venv/bin/activate
For Windows:

bash
Copy
Edit
venv\Scripts\activate
Activating the virtual environment ensures that any packages you install are confined to this specific environment, preventing interference with other Python projects.

Step 4: Install Dependencies
With the virtual environment activated, install the required dependencies by running the following command:

bash
Copy
Edit
pip install -r requirements.txt
This command installs all the necessary packages and libraries needed to run the Flux system.

Step 5: Apply Migrations
Flux uses Django’s migration system to set up the database. Run the following command to apply the necessary migrations and create the database structure:

bash
Copy
Edit
python manage.py migrate
This will set up all the tables and relationships needed by Flux.

Step 6: Create a Superuser
To access the administrative panel of Flux, you'll need to create a superuser account. This account will have full administrative privileges and allow you to manage the system. You can create a superuser by running:

bash
Copy
Edit
python manage.py createsuperuser
You’ll be prompted to enter a username, email, and password. Make sure to choose strong credentials.

Step 7: Run the Development Server
After setting everything up, start the development server by running:

bash
Copy
Edit
python manage.py runserver
This will start the Django development server locally. By default, the server will run on http://127.0.0.1:8000/.

You can now access the Flux system in your browser. To access the admin panel, navigate to:

text
Copy
Edit
http://127.0.0.1:8000/admin/
Additional Configuration and Customization
Flux is built to be flexible and can be customized according to your specific needs. If you wish to integrate the system with other platforms, modify the user interface, or add additional features, you can easily extend it by modifying the source code.

<b> Some additional configurations to consider include:</b>

Email Notifications: Configure email settings in settings.py to receive low-stock alerts and other important notifications.

Custom Reports: Modify or extend the reporting functionality to meet specific lab requirements or to include additional data points.

## Conclusion
The Facility Logistics Utilization Xpert (Flux) is a powerful inventory management tool designed to streamline the logistics operations of a Genomics and Bioinformatics Core Facility Lab. It provides an efficient and user-friendly way to manage and track lab products, ensuring that your team has everything they need to perform groundbreaking research.

With Flux, you can reduce manual errors, improve inventory tracking, and ensure that your lab’s resources are always in optimal condition. The easy-to-use interface, combined with robust features like real-time stock tracking, product management, and reporting, makes Flux a perfect solution for modern labs.

