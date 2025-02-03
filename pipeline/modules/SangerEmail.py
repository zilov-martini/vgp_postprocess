import os
import smtplib
from email.message import EmailMessage

def send_email(main_recipients, cc, subject, message):

	msg = EmailMessage()

	msg['From'] = os.environ.get('USER') + '@sanger.ac.uk'

	msg['To'] = ','.join(main_recipients)
	msg["Cc"] = ','.join(cc)
	msg['Subject'] = subject
	msg.set_content(message)

	server = smtplib.SMTP('mail.internal.sanger.ac.uk', 25)

	server.send_message(msg)
	server.quit()

	print("Successfully sent email to %s:" % (msg['To']))

