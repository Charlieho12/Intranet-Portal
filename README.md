# 📄 Travel Authority System Documentation

---

## Table of Contents

1. Overview
2. System Features
3. User Roles
4. System Flow
5. Technical Setup
6. How to Use (User Manual)
7. Admin/IT Operations
8. Troubleshooting
9. FAQ
10. Support

---

## Overview

The Travel Authority System is a web-based application for managing Travel Order Authority (TOA), Official Business (OB), and Cash Advance requests, including multi-level approvals, notifications, and reporting.  
It is built using Flask (Python), MongoDB, and Flask-Mail for email notifications.

---

## System Features

- User Authentication: Secure login and signup for employees and approvers.
- TOA/OB Request: Employees can file, edit, and track Travel Order Authority and Official Business requests.
- Cash Advance: Request, approve, and release cash advances linked to TOA/OB.
- Multi-level Approval: Dynamic routing to supervisors, managers, and executives.
- Send Back & Edit: Approvers can send back requests for revision; employees can edit and resubmit.
- Email Notifications: Automatic emails for approvals, rejections, send-backs, and releases.
- Reporting: Final reports for completed TOA/OB.
- Audit Trail: Status tracking and remarks for each approval step.

---

## User Roles

- Employee: Files requests, edits, and tracks their status.
- Approver: Approves, rejects, or sends back requests.
- Treasury: Releases cash advances.
- Admin/IT: Manages users, system settings, and troubleshooting.

---

## System Flow

1. Employee files a TOA/OB request.
2. Approvers receive email notifications and approve/reject/send back.
3. If sent back, employee edits and resubmits.
4. If approved, employee may request a cash advance.
5. Treasury releases cash advance after all approvals.
6. Final report is generated and available for download/print.

---

## Technical Setup

### Prerequisites

- Python 3.8+
- MongoDB
- Git
- (Optional) Virtualenv

## How to Use (User Manual)

1. **Login / Signup**
   - Go to `/login` to sign in.
   - New users can register via `/signup`.

2. **File a TOA or OB**
   - Click “New Travel Order” or “Official Business”.
   - Fill in all required fields (dates, destinations, purpose, etc.).
   - Submit the form.

3. **Approval Process**
   - Approvers receive an email with a link to approve/reject/send back.
   - Approvers can add remarks.
   - Status is updated in real-time.

4. **Send Back & Edit**
   - If sent back, employee receives an email and can edit the request.
   - After editing, resubmit for approval.

5. **Cash Advance**
   - After TOA/OB approval, request a cash advance if needed.
   - Fill in the cash advance form and submit.
   - Follows a similar approval process.

6. **Release**
   - Treasury users can mark cash advances as released.
   - Employee receives an email notification.

7. **Reports**
   - After completion, download or print the final report from the system.

---

## Admin/IT Operations

- User Management: Add, edit, or remove users in the MongoDB `users` collection.
- Backup: Regularly back up the MongoDB database.
- Logs: Check server logs for errors or email issues.
- Configuration: Update SMTP/email settings in app.py as needed.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Cannot login | Check MongoDB connection and user credentials. |
| Email not sending | Verify SMTP settings and Gmail app password. Check for errors in the console. |
| Approval links not working | Ensure Flask server is running and accessible. |
| Page not loading | Check for Python errors in the terminal. |
| Git not updating | Remember to `git add`, `git commit`, and `git push` after changes. |

---

## FAQ

**Q: How do I reset a user’s password?**  
A: Update the `password` field in the `users` collection (hashed with bcrypt).

**Q: How do I add a new approver?**  
A: Add the approver’s details in the `users` collection with the correct position and department.

**Q: Can I use a different email provider?**  
A: Yes, update the `MAIL_SERVER`, `MAIL_PORT`, etc., in app.py.

---

## Support

For technical support, contact your IT administrator or the project maintainer.
