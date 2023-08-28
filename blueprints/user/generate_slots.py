from datetime import datetime, timedelta

def generate_slots(schedule, selected_date):
    
    # Extract morning and evening session timings if they exist
    morning_start = schedule.get('morning')
    evening_start = schedule.get('evening')

    # Convert timings to datetime objects
    if morning_start:
        morning_start_time = datetime.strptime(morning_start.split('-')[0], '%I%p')
        morning_end_time = datetime.strptime(morning_start.split('-')[1], '%I%p')
    if evening_start:
        evening_start_time = datetime.strptime(evening_start.split('-')[0], '%I%p')
        evening_end_time = datetime.strptime(evening_start.split('-')[1], '%I%p')

    # Calculate the total available time in minutes for each session
    morning_available_time = (morning_end_time - morning_start_time).seconds // 60 if morning_start else 0
    evening_available_time = (evening_end_time - evening_start_time).seconds // 60 if evening_start else 0

    # Calculate the ratio of morning and evening available time
    total_available_time = morning_available_time + evening_available_time
    morning_ratio = morning_available_time / total_available_time if total_available_time != 0 else 0
    evening_ratio = evening_available_time / total_available_time if total_available_time != 0 else 0

    # Get the limit
    limit = int(schedule['limit'])
    # Calculate the number of slots for morning and evening based on ratio
    morning_slots = round(limit * morning_ratio)
    evening_slots = round(limit * evening_ratio)

    # Calculate the average time per appointment (in minutes)
    morning_avg_time_per_appointment = morning_available_time / morning_slots if morning_slots != 0 else 0
    evening_avg_time_per_appointment = evening_available_time / evening_slots if evening_slots != 0 else 0

    # Round the average time per appointment to the nearest multiple of 5
    morning_avg_time_per_appointment = round(morning_avg_time_per_appointment / 5) * 5
    evening_avg_time_per_appointment = round(evening_avg_time_per_appointment / 5) * 5

    # Calculate time slots for morning session
    morning_time_slots = []
    if morning_start:
        current_time = morning_start_time
        for _ in range(morning_slots):
            if current_time + timedelta(minutes=morning_avg_time_per_appointment) <= morning_end_time + timedelta(minutes=morning_avg_time_per_appointment):
                morning_time_slots.append(current_time.strftime('%I:%M %p'))
                current_time += timedelta(minutes=morning_avg_time_per_appointment)

    # Calculate time slots for evening session
    evening_time_slots = []
    if evening_start:
        current_time = evening_start_time
        for _ in range(evening_slots):
            if current_time + timedelta(minutes=evening_avg_time_per_appointment) <= evening_end_time + + timedelta(minutes=evening_avg_time_per_appointment):
                evening_time_slots.append(current_time.strftime('%I:%M %p'))
                current_time += timedelta(minutes=evening_avg_time_per_appointment)

    # Combine morning and evening time slots
    time_slots = morning_time_slots + evening_time_slots

    # Convert the selected date string to a datetime.date object
    selected_date = datetime.strptime(selected_date, '%Y-%m-%d').date()

    # Get the current date and time
    current_datetime = datetime.now().date()

    # Check if the selected date is today's date
    if selected_date == current_datetime:
        current_time = datetime.now().time()

        # Filter time slots that are in the future
        time_slots = [slot for slot in time_slots if datetime.strptime(slot, '%I:%M %p').time() > current_time]
    else:
        time_slots = time_slots

    return time_slots