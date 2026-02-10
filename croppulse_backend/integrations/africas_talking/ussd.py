# USSD Menu System for Nokia 3310

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from apps.farmers.models import Farmer
from apps.farms.models import Farm
from integrations.africas_talking.sms import SMSService
import logging

logger = logging.getLogger(__name__)

@csrf_exempt
def ussd_callback(request):
    """Handle USSD requests from Africa's Talking"""
    
    if request.method != 'POST':
        return HttpResponse("Method not allowed", status=405)
    
    # Get USSD parameters
    session_id = request.POST.get('sessionId', '')
    service_code = request.POST.get('serviceCode', '')
    phone_number = request.POST.get('phoneNumber', '')
    text = request.POST.get('text', '')
    
    # Parse user input
    user_input = text.split('*')
    level = len(user_input)
    
    # Generate response
    response = generate_ussd_menu(phone_number, user_input, level)
    
    return HttpResponse(response, content_type='text/plain')


def generate_ussd_menu(phone_number, user_input, level):
    """Generate USSD menu based on user input"""
    
    if level == 1 and user_input[0] == '':
        # Main menu
        return "CON Welcome to CropPulse\n1. Report Weather\n2. My Farm Status\n3. My Credit Score\n4. Harvest Alert\n5. Help"
    
    elif level == 2:
        choice = user_input[1]
        
        if choice == '1':
            # Weather reporting
            return "CON Report Weather:\n1. Clear/Sunny\n2. Cloudy\n3. Light Rain\n4. Heavy Rain\n5. Storm"
        
        elif choice == '2':
            # Farm status
            try:
                farmer = Farmer.objects.get(user__phone_number=phone_number)
                farms = Farm.objects.filter(farmer=farmer)
                
                if not farms.exists():
                    return "END You have no farms registered. Visit our office to register."
                
                farm = farms.first()
                return f"END Farm: {farm.name}\nCrop: {farm.crop_type}\nStatus: {'Verified' if farm.is_verified else 'Pending'}"
            except:
                return "END Farmer not found. Please register first."
        
        elif choice == '3':
            # Credit score
            try:
                farmer = Farmer.objects.get(user__phone_number=phone_number)
                from apps.scoring.models import PulseScore
                score = PulseScore.objects.get(farmer=farmer)
                grade = get_grade(score.score)
                return f"END Your Credit Score:\n{score.score}/1000\nGrade: {grade}"
            except:
                return "END Score not available yet."
        
        elif choice == '4':
            # Harvest alert
            return "CON Harvest Alert:\n1. Check Optimal Date\n2. Road Conditions\n3. Loss Estimate"
        
        elif choice == '5':
            # Help
            return "END CropPulse Help:\nCall: 0800-CROP-PULSE\nSMS: 'HELP' to 40404"
    
    elif level == 3:
        main_choice = user_input[1]
        sub_choice = user_input[2]
        
        if main_choice == '1':
            # Submit weather report
            weather_map = {
                '1': 'clear',
                '2': 'cloudy',
                '3': 'light_rain',
                '4': 'heavy_rain',
                '5': 'storm'
            }
            
            weather = weather_map.get(sub_choice, 'clear')
            
            try:
                farmer = Farmer.objects.get(user__phone_number=phone_number)
                from apps.farmers.models_verification import GroundTruthReport
                from django.utils import timezone
                
                GroundTruthReport.objects.create(
                    farmer=farmer,
                    weather_condition=weather,
                    temperature_feel='normal',
                    rainfall_amount='none' if weather in ['clear', 'cloudy'] else 'moderate',
                    weather_time=timezone.now()
                )
                
                return "END Thank you! Weather report submitted. You earned 2 points."
            except:
                return "END Error submitting report. Please try again."
        
        elif main_choice == '4':
            # Harvest timing
            try:
                farmer = Farmer.objects.get(user__phone_number=phone_number)
                farm = Farm.objects.filter(farmer=farmer).first()
                
                if not farm:
                    return "END No farm found."
                
                from apps.farms.services.logistics import LogisticsIntelligence
                logistics = LogisticsIntelligence()
                
                if sub_choice == '1':
                    # Optimal date
                    analysis = logistics.analyze_harvest_window(farm.id)
                    optimal = analysis.get('optimal_harvest_date')
                    return f"END Optimal Harvest:\n{optimal if optimal else 'No good days in next 7 days'}"
                
                elif sub_choice == '2':
                    # Road conditions
                    analysis = logistics.analyze_harvest_window(farm.id)
                    road = analysis.get('road_risk', {})
                    return f"END Road Status:\n{road.get('accessibility', 'Unknown')}"
                
                elif sub_choice == '3':
                    # Loss estimate
                    estimate = logistics.estimate_post_harvest_loss(farm.id, delay_days=3)
                    return f"END 3-Day Delay Loss:\n{estimate['estimated_loss_percentage']:.1f}%"
            except:
                return "END Service unavailable."
    
    return "END Invalid option. Please try again."


def get_grade(score):
    """Get letter grade"""
    if score >= 800:
        return 'A'
    elif score >= 700:
        return 'B'
    elif score >= 600:
        return 'C'
    elif score >= 500:
        return 'D'
    return 'F'
