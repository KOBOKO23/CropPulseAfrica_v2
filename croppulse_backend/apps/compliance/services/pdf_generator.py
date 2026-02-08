# compliance/services/pdf_generator.py
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, PageBreak, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from io import BytesIO
from django.core.files import File
from django.conf import settings
import os
from datetime import datetime


class PDFGenerator:
    """Generate EUDR compliance PDF documents"""
    
    def __init__(self):
        self.page_width, self.page_height = A4
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles"""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a365d'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
        
        # Subtitle style
        self.styles.add(ParagraphStyle(
            name='SubTitle',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#2c5282'),
            spaceAfter=12,
            spaceBefore=12,
            fontName='Helvetica-Bold'
        ))
        
        # Section header
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading3'],
            fontSize=12,
            textColor=colors.HexColor('#2d3748'),
            spaceAfter=8,
            spaceBefore=8,
            fontName='Helvetica-Bold',
            backColor=colors.HexColor('#edf2f7'),
            borderPadding=5
        ))
        
        # Body text
        self.styles.add(ParagraphStyle(
            name='CustomBody',
            parent=self.styles['Normal'],
            fontSize=10,
            alignment=TA_JUSTIFY,
            spaceAfter=6
        ))
        
        # Small text
        self.styles.add(ParagraphStyle(
            name='SmallText',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#718096')
        ))
    
    def _add_header(self, canvas, doc):
        """Add header to each page"""
        canvas.saveState()
        
        # Add logo if exists
        logo_path = os.path.join(settings.STATIC_ROOT, 'images', 'logo.png')
        if os.path.exists(logo_path):
            canvas.drawImage(
                logo_path,
                30, self.page_height - 50,
                width=100, height=30,
                preserveAspectRatio=True
            )
        
        # Add title
        canvas.setFont('Helvetica-Bold', 10)
        canvas.setFillColor(colors.HexColor('#1a365d'))
        canvas.drawString(
            150, self.page_height - 40,
            "EUDR Digital Export Passport"
        )
        
        # Add line
        canvas.setStrokeColor(colors.HexColor('#e2e8f0'))
        canvas.setLineWidth(1)
        canvas.line(30, self.page_height - 60, self.page_width - 30, self.page_height - 60)
        
        canvas.restoreState()
    
    def _add_footer(self, canvas, doc):
        """Add footer to each page"""
        canvas.saveState()
        
        # Add line
        canvas.setStrokeColor(colors.HexColor('#e2e8f0'))
        canvas.setLineWidth(1)
        canvas.line(30, 50, self.page_width - 30, 50)
        
        # Add page number
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.HexColor('#718096'))
        page_num = canvas.getPageNumber()
        text = f"Page {page_num}"
        canvas.drawRightString(self.page_width - 30, 35, text)
        
        # Add generation date
        gen_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        canvas.drawString(30, 35, f"Generated: {gen_date}")
        
        # Add verification URL
        canvas.setFont('Helvetica', 7)
        canvas.drawCentredString(
            self.page_width / 2, 25,
            "Verify at: https://verify.croppulse.com"
        )
        
        canvas.restoreState()
    
    def generate_export_passport(self, passport, language='en'):
        """
        Generate export passport PDF
        
        Args:
            passport: ExportPassport instance
            language: Language code for translation
        
        Returns:
            File object containing PDF
        """
        buffer = BytesIO()
        
        # Create document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=30,
            leftMargin=30,
            topMargin=80,
            bottomMargin=70,
        )
        
        # Container for elements
        elements = []
        
        # Title
        title = Paragraph(
            "EUDR Digital Export Passport",
            self.styles['CustomTitle']
        )
        elements.append(title)
        elements.append(Spacer(1, 12))
        
        # Passport ID prominently displayed
        passport_id_table = Table(
            [[Paragraph(
                f"<b>Passport ID:</b> {passport.passport_id}",
                self.styles['SubTitle']
            )]],
            colWidths=[self.page_width - 60]
        )
        passport_id_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#edf2f7')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('BOX', (0, 0), (-1, -1), 2, colors.HexColor('#2c5282')),
        ]))
        elements.append(passport_id_table)
        elements.append(Spacer(1, 20))
        
        # QR Code
        if passport.qr_code:
            try:
                qr_img = Image(passport.qr_code.path, width=2*inch, height=2*inch)
                qr_table = Table([[qr_img]], colWidths=[self.page_width - 60])
                qr_table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ]))
                elements.append(qr_table)
                elements.append(Spacer(1, 12))
            except:
                pass
        
        # Section 1: Operator Information
        elements.append(Paragraph("1. OPERATOR INFORMATION", self.styles['SectionHeader']))
        operator_data = [
            ['Operator Name:', passport.operator_name],
            ['EORI Number:', passport.operator_eori or 'N/A'],
            ['DDS Reference:', passport.dds_reference_number],
        ]
        operator_table = self._create_info_table(operator_data)
        elements.append(operator_table)
        elements.append(Spacer(1, 12))
        
        # Section 2: Commodity Information
        elements.append(Paragraph("2. COMMODITY INFORMATION", self.styles['SectionHeader']))
        commodity_data = [
            ['Commodity Type:', passport.get_commodity_type_display()],
            ['Commodity Code:', passport.commodity_code],
            ['Harvest Season:', passport.harvest_season or 'N/A'],
            ['Estimated Production:', f"{passport.estimated_production_kg} kg" if passport.estimated_production_kg else 'N/A'],
        ]
        commodity_table = self._create_info_table(commodity_data)
        elements.append(commodity_table)
        elements.append(Spacer(1, 12))
        
        # Section 3: Farmer Information
        elements.append(Paragraph("3. FARMER INFORMATION", self.styles['SectionHeader']))
        farmer = passport.farmer
        farmer_data = [
            ['Farmer Name:', farmer.full_name],
            ['Farmer ID:', str(farmer.id)],
            ['Contact:', farmer.phone_number or 'N/A'],
        ]
        farmer_table = self._create_info_table(farmer_data)
        elements.append(farmer_table)
        elements.append(Spacer(1, 12))
        
        # Section 4: Farm & Geolocation
        elements.append(Paragraph("4. FARM & GEOLOCATION DATA", self.styles['SectionHeader']))
        farm_data = [
            ['Farm Name:', passport.farm.farm_name],
            ['Farm Size:', f"{passport.farm_size_hectares} hectares"],
            ['Centroid Coordinates:', f"{passport.centroid_latitude}, {passport.centroid_longitude}"],
            ['GPS Corner Points:', f"{len(passport.gps_coordinates)} points recorded"],
        ]
        farm_table = self._create_info_table(farm_data)
        elements.append(farm_table)
        elements.append(Spacer(1, 12))
        
        # Section 5: Land Tenure
        elements.append(Paragraph("5. LAND TENURE INFORMATION", self.styles['SectionHeader']))
        tenure_data = [
            ['Ownership Verified:', '✓ Yes' if passport.land_ownership_verified else '✗ No'],
            ['Tenure Type:', passport.get_land_tenure_type_display() if passport.land_tenure_type else 'N/A'],
            ['Document Type:', passport.get_land_document_type_display() if passport.land_document_type else 'N/A'],
        ]
        tenure_table = self._create_info_table(tenure_data)
        elements.append(tenure_table)
        elements.append(Spacer(1, 12))
        
        # Section 6: Deforestation Status
        elements.append(Paragraph("6. DEFORESTATION VERIFICATION", self.styles['SectionHeader']))
        
        # Status indicator
        status_color = self._get_status_color(passport.deforestation_status)
        status_para = Paragraph(
            f"<b>Status:</b> <font color='{status_color}'>{passport.get_deforestation_status_display()}</font>",
            self.styles['CustomBody']
        )
        elements.append(status_para)
        
        deforestation_data = [
            ['Baseline Date:', passport.baseline_date.strftime('%Y-%m-%d')],
            ['Risk Level:', passport.get_risk_level_display()],
            ['Analysis Date:', passport.satellite_analysis_date.strftime('%Y-%m-%d')],
        ]
        deforestation_table = self._create_info_table(deforestation_data)
        elements.append(deforestation_table)
        elements.append(Spacer(1, 12))
        
        # Section 7: Blockchain Verification
        if passport.blockchain_hash:
            elements.append(Paragraph("7. BLOCKCHAIN VERIFICATION", self.styles['SectionHeader']))
            blockchain_data = [
                ['Network:', passport.get_blockchain_network_display()],
                ['Hash:', passport.blockchain_hash[:20] + '...'],
                ['Transaction:', passport.blockchain_tx_hash[:20] + '...' if passport.blockchain_tx_hash else 'N/A'],
                ['Timestamp:', passport.blockchain_timestamp.strftime('%Y-%m-%d %H:%M:%S') if passport.blockchain_timestamp else 'N/A'],
            ]
            blockchain_table = self._create_info_table(blockchain_data)
            elements.append(blockchain_table)
            elements.append(Spacer(1, 12))
        
        # Section 8: Validity
        elements.append(Paragraph("8. PASSPORT VALIDITY", self.styles['SectionHeader']))
        validity_data = [
            ['Issued Date:', passport.issued_date.strftime('%Y-%m-%d')],
            ['Valid Until:', passport.valid_until.strftime('%Y-%m-%d')],
            ['Status:', '✓ Active' if passport.is_active else '✗ Inactive'],
            ['Verified:', '✓ Yes' if passport.is_verified else '⧗ Pending'],
            ['Days Remaining:', str(passport.days_until_expiry()) if not passport.is_expired() else 'EXPIRED'],
        ]
        validity_table = self._create_info_table(validity_data)
        elements.append(validity_table)
        elements.append(Spacer(1, 20))
        
        # Disclaimer
        disclaimer = Paragraph(
            "<b>DISCLAIMER:</b> This digital passport is issued in compliance with EU Regulation 2023/1115 "
            "on deforestation-free products. All data has been verified through satellite imagery analysis and "
            "on-ground verification. This document is valid only if the QR code verification succeeds and the "
            "expiry date has not passed. Any alterations to this document invalidate it.",
            self.styles['SmallText']
        )
        elements.append(disclaimer)
        
        # Build PDF
        doc.build(
            elements,
            onFirstPage=self._add_header,
            onLaterPages=self._add_header,
            canvasmaker=lambda *args, **kwargs: self._add_footer_to_canvas(*args, **kwargs)
        )
        
        # Get PDF data
        pdf_data = buffer.getvalue()
        buffer.close()
        
        # Create File object
        filename = f'passport_{passport.passport_id}.pdf'
        pdf_file = File(BytesIO(pdf_data), name=filename)
        
        # Save to passport
        passport.pdf_document.save(filename, pdf_file, save=True)
        
        return pdf_file
    
    def _create_info_table(self, data):
        """Create a styled info table"""
        table = Table(data, colWidths=[150, self.page_width - 210])
        table.setStyle(TableStyle([
            ('FONT', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONT', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#2d3748')),
            ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#4a5568')),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#f7fafc')]),
        ]))
        return table
    
    def _get_status_color(self, status):
        """Get color for deforestation status"""
        colors_map = {
            'CLEAR': '#48bb78',  # Green
            'UNDER_REVIEW': '#ed8936',  # Orange
            'FLAGGED': '#f56565',  # Red
            'REMEDIATED': '#4299e1',  # Blue
        }
        return colors_map.get(status, '#718096')
    
    def _add_footer_to_canvas(self, canvas, doc):
        """Custom canvas maker to add footer"""
        canvas.saveState()
        self._add_footer(canvas, doc)
        canvas.restoreState()
        return canvas
    
    def generate_deforestation_report(self, deforestation_check):
        """
        Generate deforestation analysis report PDF
        
        Args:
            deforestation_check: DeforestationCheck instance
        
        Returns:
            File object containing PDF
        """
        buffer = BytesIO()
        
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=30,
            leftMargin=30,
            topMargin=80,
            bottomMargin=70,
        )
        
        elements = []
        
        # Title
        title = Paragraph(
            "Deforestation Analysis Report",
            self.styles['CustomTitle']
        )
        elements.append(title)
        elements.append(Spacer(1, 20))
        
        # Farm Information
        elements.append(Paragraph("FARM INFORMATION", self.styles['SectionHeader']))
        farm_data = [
            ['Farm Name:', deforestation_check.farm.farm_name],
            ['Farmer:', deforestation_check.farm.farmer.full_name],
            ['Analysis Date:', deforestation_check.check_date.strftime('%Y-%m-%d')],
            ['Check Type:', deforestation_check.get_check_type_display()],
        ]
        farm_table = self._create_info_table(farm_data)
        elements.append(farm_table)
        elements.append(Spacer(1, 12))
        
        # Analysis Period
        elements.append(Paragraph("ANALYSIS PERIOD", self.styles['SectionHeader']))
        period_data = [
            ['Start Date:', deforestation_check.analysis_start_date.strftime('%Y-%m-%d')],
            ['End Date:', deforestation_check.analysis_end_date.strftime('%Y-%m-%d')],
            ['Baseline Date:', deforestation_check.baseline_date.strftime('%Y-%m-%d')],
        ]
        period_table = self._create_info_table(period_data)
        elements.append(period_table)
        elements.append(Spacer(1, 12))
        
        # Results
        elements.append(Paragraph("ANALYSIS RESULTS", self.styles['SectionHeader']))
        
        result_color = self._get_result_color(deforestation_check.result)
        result_para = Paragraph(
            f"<b>Result:</b> <font color='{result_color}'>{deforestation_check.get_result_display()}</font>",
            self.styles['CustomBody']
        )
        elements.append(result_para)
        
        results_data = [
            ['Deforestation Detected:', '✓ Yes' if deforestation_check.deforestation_detected else '✗ No'],
            ['Forest Cover:', f"{deforestation_check.forest_cover_percentage:.2f}%"],
            ['Baseline Cover:', f"{deforestation_check.baseline_forest_cover:.2f}%" if deforestation_check.baseline_forest_cover else 'N/A'],
            ['Change:', f"{deforestation_check.change_in_forest_cover:+.2f}%"],
            ['Forest Loss:', f"{deforestation_check.forest_loss_hectares} ha" if deforestation_check.forest_loss_hectares else 'N/A'],
            ['Risk Score:', f"{deforestation_check.risk_score}/100"],
            ['Confidence:', f"{deforestation_check.confidence_score:.2%}" if deforestation_check.confidence_score else 'N/A'],
        ]
        results_table = self._create_info_table(results_data)
        elements.append(results_table)
        elements.append(Spacer(1, 12))
        
        # Satellite Data
        elements.append(Paragraph("SATELLITE DATA", self.styles['SectionHeader']))
        satellite_data = [
            ['Provider:', deforestation_check.get_satellite_provider_display()],
            ['Cloud Cover:', f"{deforestation_check.cloud_cover_percentage:.1f}%" if deforestation_check.cloud_cover_percentage else 'N/A'],
            ['NDVI Baseline:', f"{deforestation_check.ndvi_baseline:.3f}" if deforestation_check.ndvi_baseline else 'N/A'],
            ['NDVI Current:', f"{deforestation_check.ndvi_current:.3f}" if deforestation_check.ndvi_current else 'N/A'],
            ['NDVI Change:', f"{deforestation_check.ndvi_change:+.3f}" if deforestation_check.ndvi_change else 'N/A'],
        ]
        satellite_table = self._create_info_table(satellite_data)
        elements.append(satellite_table)
        
        # Build PDF
        doc.build(
            elements,
            onFirstPage=self._add_header,
            onLaterPages=self._add_header
        )
        
        pdf_data = buffer.getvalue()
        buffer.close()
        
        filename = f'deforestation_report_{deforestation_check.id}.pdf'
        return File(BytesIO(pdf_data), name=filename)
    
    def _get_result_color(self, result):
        """Get color for analysis result"""
        colors_map = {
            'CLEAR': '#48bb78',
            'WARNING': '#ed8936',
            'VIOLATION': '#f56565',
            'INCONCLUSIVE': '#718096',
        }
        return colors_map.get(result, '#718096')