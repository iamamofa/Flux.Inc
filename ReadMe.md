# Flux - Django Inventory System

Flux is a Django-based inventory management system designed to streamline and organize inventory-related operations for businesses. It provides a user-friendly interface for managing products, tracking stock levels, and generating reports.

## Features

- **Product Management:** Easily add, edit, and delete products in the inventory.
- **Stock Tracking:** Real-time tracking of stock levels for each product.
- **User Authentication:** Secure user authentication for different roles (Admin, Staff).
- **Reports:** Generate and view reports on product performance, sales, and stock levels.
- **Search and Filters:** Efficient search and filtering options to quickly locate products.

## Getting Started

### Prerequisites

<pre> 
```
Python  
```
</pre>

### Installation

1. Clone the repository:

   <pre>
```
git clone https://github.com/iamamofa/flux.git
   cd flux
```
</pre>

## Create a virtual environment:

1.  ``` python -m venv venv ``` 

2. 
 ```source venv/bin/activate  # Linux/macOS ```
# or

``` venv\Scripts\activate   #Windows Users ```

## Install dependencies:

``` pip install -r requirements.txt ```

## Apply migrations:

``` python manage.py migrate ```
## Create a superuser for the admin panel:
 
``` python manage.py createsuperuser ```

## Run the development server:
```python manage.py runserver```
###### Access the admin panel at ```http://127.0.0.1:8000/admin/ ``` using the superuser credentials.
