# IT Management System (Flask + SQLite)

A functional system for IT departments to manage assets, staff assignments, expenditures, recurring payments, ISPs & downtimes, and reports.

## Features
- Login/Logout (Flask-Login) with default admin (admin / ChangeMe123!)
- Staff module
- Assets with associated components (e.g., desktop -> keyboard, mouse)
- Assign assets to staff; track history
- Repairs/Maintenance log
- Expenditures with doc type and reference (e.g., Invoice, LPO, M-Pesa ref)
- Budgeting views via expenditure totals
- Recurring payments with upcoming alerts on dashboard
- ISPs: monthly fee, downtime logging, net pay calculation (prorated by downtime hours)
- Reports: Who-has-what; Expenditures; ISP Net Pay

## Run
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
Login: admin / ChangeMe123! (change immediately under Users).
