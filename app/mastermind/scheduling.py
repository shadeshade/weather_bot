import os

import pytz
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler

from app import bot, db
from app.mastermind.formating import get_today_weather_info, get_phenomenon_info
from app.models import User, Reminder

TIME_ZONE_MSK = pytz.timezone('Europe/Moscow')

jobstores = {
    'default': SQLAlchemyJobStore(url=os.getenv("DATABASE_URL"))
}
scheduler = BackgroundScheduler()
scheduler.configure(jobstores=jobstores, timezone=TIME_ZONE_MSK)
if scheduler.state == 0:
    scheduler.start()


# Handle '/daily' (setting a daily reminder)
def set_daily(new_reminder, hours, minutes, ):
    job = scheduler.add_job(send_daily_reminder, args=[new_reminder.user_id, f'{hours}.{minutes}'],
                            trigger='cron', hour=hours, minute=minutes)
    new_reminder.job_id = job.id
    db.session.commit()


# Handle '/daily' (sending a reminder)
def send_daily_reminder(user_id, set_time):
    user = User.query.filter_by(id=user_id).first()
    response_msg = get_today_weather_info(user.city_name, user.language, set_time)

    bot.send_message(user.chat_id, text=response_msg, parse_mode='html')


# Handle phenomenon reminder
def set_phenomenon_time(new_reminder, hours, minutes):
    job = scheduler.add_job(send_phenomenon_reminder, args=[new_reminder.user_id],
                            trigger='cron', hour=hours, minute=minutes)
    new_reminder.job_id = job.id
    db.session.commit()


# Handle '/phenomena' (sending a phenomenon reminder)
def send_phenomenon_reminder(user_id):
    user = User.query.filter_by(id=user_id).first()
    response_msg = get_phenomenon_info(user)
    if response_msg:
        bot.send_message(user.chat_id, text=response_msg, parse_mode='html')


# Handle delete phenomenon reminder
def delete_ph_time_jobs(user_id):
    ph_reminders = Reminder.query.filter_by(user_id=user_id, is_phenomenon=True).all()
    for reminder in ph_reminders:
        scheduler.remove_job(job_id=reminder.job_id, jobstore='default')
