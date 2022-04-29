import smtplib
import time
#
import swConfig
config_debug=False


fromaddr = swConfig.EMAIL_FROM
toaddrs = swConfig.EMAIL_TO
mail_server = swConfig.EMAIL_SERVER
mail_pass = swConfig.EMAIL_PASS
mail_port = swConfig.EMAIL_PORT


message_str = """\
From: Logger Fotovoltaico <%s>
To: <%s>
Subject: %s
MIME-Version: 1.0
Content-Type: text/html
Date: %s


%s
</br>
"""
email_sent = "" 

def send_mail(content):
    global message_str
    global email_sent
    if email_sent == content:
        return
    
    email_sent = content 
    subject = "Solar logger reporting"
        
    tstr = time.strftime("%d %b %Y %H:%M:%S %z")
    message = message_str % (fromaddr, toaddrs, subject,tstr, content)
    try:
        server = smtplib.SMTP_SSL(host=mail_server, port=mail_port)
        if config_debug:
            server.set_debuglevel(1)

        server.login(fromaddr, mail_pass)
        server.sendmail(fromaddr, toaddrs, message)
        server.quit
    except Exception as e:
        print("mailing error: %s" % str(e))


