# Bank Credit Report Generator

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import inch
from io import BytesIO
from django.utils import timezone

class BankCreditReportGenerator:
    """Generate PDF credit reports for banks"""
    
    def generate_report(self, farmer):
        """Generate comprehensive credit report"""
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        elements = []
        styles = getSampleStyleSheet()
        
        # Title
        title = Paragraph(f"<b>Climate-Smart Credit Report</b>", styles['Title'])
        elements.append(title)
        elements.append(Spacer(1, 0.2*inch))
        
        # Farmer Info
        info_data = [
            ['Farmer Name:', f"{farmer.first_name} {farmer.last_name}"],
            ['Pulse ID:', farmer.pulse_id],
            ['County:', farmer.county],
            ['Years Farming:', str(farmer.years_farming)],
            ['Primary Crop:', farmer.primary_crop],
            ['Report Date:', timezone.now().strftime('%Y-%m-%d')],
        ]
        
        info_table = Table(info_data, colWidths=[2*inch, 4*inch])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ]))
        elements.append(info_table)
        elements.append(Spacer(1, 0.3*inch))
        
        # Credit Score
        try:
            from apps.scoring.models import PulseScore
            score = PulseScore.objects.get(farmer=farmer)
            
            score_data = [
                ['Overall Score:', f"{score.score}/1000", self._get_grade(score.score)],
                ['Farm Size Score:', f"{score.farm_size_score}/100", ''],
                ['Crop Health Score:', f"{score.crop_health_score}/100", ''],
                ['Climate Risk Score:', f"{score.climate_risk_score}/100", ''],
                ['Payment History:', f"{score.payment_history_score}/100", ''],
                ['Deforestation Score:', f"{score.deforestation_score}/100", ''],
            ]
            
            score_table = Table(score_data, colWidths=[2.5*inch, 2*inch, 1.5*inch])
            score_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.green),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            elements.append(Paragraph("<b>Credit Score Breakdown</b>", styles['Heading2']))
            elements.append(Spacer(1, 0.1*inch))
            elements.append(score_table)
            elements.append(Spacer(1, 0.3*inch))
            
        except:
            pass
        
        # Verified Actions
        from apps.farmers.models_verification import ProofOfAction
        actions = ProofOfAction.objects.filter(farmer=farmer, verified=True).order_by('-action_date')[:10]
        
        if actions.exists():
            elements.append(Paragraph("<b>Verified Actions (Last 10)</b>", styles['Heading2']))
            elements.append(Spacer(1, 0.1*inch))
            
            action_data = [['Date', 'Action Type', 'Points', 'Blockchain']]
            for action in actions:
                action_data.append([
                    action.action_date.strftime('%Y-%m-%d'),
                    action.get_action_type_display(),
                    str(action.points_earned),
                    'Yes' if action.blockchain_hash else 'No'
                ])
            
            action_table = Table(action_data, colWidths=[1.5*inch, 2*inch, 1*inch, 1.5*inch])
            action_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            elements.append(action_table)
        
        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        return buffer
    
    def _get_grade(self, score):
        """Get letter grade from score"""
        if score >= 800:
            return 'A (Excellent)'
        elif score >= 700:
            return 'B (Good)'
        elif score >= 600:
            return 'C (Fair)'
        elif score >= 500:
            return 'D (Poor)'
        else:
            return 'F (Very Poor)'
