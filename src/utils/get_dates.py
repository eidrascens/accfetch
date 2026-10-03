from datetime import datetime


def cdate():
    return datetime.now().strftime("%Y-%m-%d")

def sdate():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
