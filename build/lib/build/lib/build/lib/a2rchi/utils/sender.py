from a2rchi.utils.env import read_secret

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, parseaddr, getaddresses

import smtplib


class Sender:
    """A class to send emails in an uncomplicated fashion."""

    def __init__(self):
        """
        Give it a name and generate a conncetion to the database (should be a singleton).
        """
        self.server_name = read_secret('SENDER_SERVER')
        self.port = read_secret('SENDER_PORT')
        self.user = read_secret('SENDER_USER')
        self.password = read_secret('SENDER_PW')
        self.reply_to = read_secret('SENDER_REPLYTO')

        print(f" Open smtp (SERVER:{self.server_name} PORT:{self.port} U:{self.user} P:*********)")


    def send_message(self, to, cc, subject, body):

        #start and login to SMTP server
        self.server = smtplib.SMTP(self.server_name, self.port)
        self.server.starttls()
        self.server.login(self.user, self.password)

        # generate the message
        msg = MIMEMultipart()
        msg['To'] = to
        msg['CC'] = cc
        msg['Subject'] = subject
        if self.reply_to:
            msg.add_header('reply-to', self.reply_to)

        # show what we are going to do
        print(f" Sending message - TO: {to}, CC: {cc}, REPLYTO: {self.reply_to}")
        print(f" ===============\n SUBJECT: {subject}")
        print(f" BODY:\n{body}")

        # Prepare the recipient list
        recipient_list = []
        if to:
            recipient_list.extend([
            formataddr(addr) for addr in getaddresses([to])
            ])

        if cc:
            recipient_list.extend([
            formataddr(addr) for addr in getaddresses([cc])
            ])

        print("Recipient List:", recipient_list)
        smtp_recipient_list = [addr[1] for addr in getaddresses([to, cc]) if addr[1]]
        print("SMTP Recipient List:", smtp_recipient_list)

        # Send the email
        msg.attach(MIMEText(body, 'plain'))
        self.server.sendmail(self.user, recipient_list, msg.as_string())

        #finally, quit the server
        self.server.quit()

        return
