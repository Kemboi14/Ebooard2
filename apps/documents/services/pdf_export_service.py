"""
PDF export service for generating PDF documents from meeting minutes, reports, and other content.
"""

from django.template.loader import render_to_string
from django.utils import timezone
from weasyprint import HTML, CSS
from io import BytesIO
import logging

logger = logging.getLogger(__name__)


class PDFExportService:
    """Service for generating PDF documents from various sources"""
    
    @staticmethod
    def generate_meeting_minutes_pdf(meeting_minutes):
        """
        Generate PDF for meeting minutes.
        
        Args:
            meeting_minutes: MeetingMinutes instance
            
        Returns:
            BytesIO: PDF file as bytes
        """
        try:
            context = {
                'meeting': meeting_minutes.meeting,
                'minutes': meeting_minutes,
                'current_date': timezone.now(),
                'portal_name': 'Enwealth Governance Portal',
            }
            
            html_content = render_to_string('documents/pdf/meeting_minutes_pdf.html', context)
            
            # CSS for styling
            css_content = render_to_string('documents/pdf/pdf_styles.css')
            css = CSS(string=css_content)
            
            # Generate PDF
            html = HTML(string=html_content, base_url='')
            pdf_file = html.write_pdf(stylesheets=[css])
            
            return BytesIO(pdf_file)
            
        except Exception as e:
            logger.error(f"Error generating meeting minutes PDF: {str(e)}")
            raise
    
    @staticmethod
    def generate_board_evaluation_pdf(board_evaluation):
        """
        Generate PDF for board evaluation report.
        
        Args:
            board_evaluation: BoardEvaluation instance
            
        Returns:
            BytesIO: PDF file as bytes
        """
        try:
            context = {
                'evaluation': board_evaluation,
                'director_evaluations': board_evaluation.director_evaluations.all(),
                'current_date': timezone.now(),
                'portal_name': 'Enwealth Governance Portal',
            }
            
            html_content = render_to_string('documents/pdf/board_evaluation_pdf.html', context)
            
            css_content = render_to_string('documents/pdf/pdf_styles.css')
            css = CSS(string=css_content)
            
            html = HTML(string=html_content, base_url='')
            pdf_file = html.write_pdf(stylesheets=[css])
            
            return BytesIO(pdf_file)
            
        except Exception as e:
            logger.error(f"Error generating board evaluation PDF: {str(e)}")
            raise
    
    @staticmethod
    def generate_compliance_report_pdf(compliance_data, period_start, period_end):
        """
        Generate PDF for compliance report.
        
        Args:
            compliance_data: Dictionary with compliance metrics
            period_start: Start date of reporting period
            period_end: End date of reporting period
            
        Returns:
            BytesIO: PDF file as bytes
        """
        try:
            context = {
                'compliance_data': compliance_data,
                'period_start': period_start,
                'period_end': period_end,
                'current_date': timezone.now(),
                'portal_name': 'Enwealth Governance Portal',
            }
            
            html_content = render_to_string('documents/pdf/compliance_report_pdf.html', context)
            
            css_content = render_to_string('documents/pdf/pdf_styles.css')
            css = CSS(string=css_content)
            
            html = HTML(string=html_content, base_url='')
            pdf_file = html.write_pdf(stylesheets=[css])
            
            return BytesIO(pdf_file)
            
        except Exception as e:
            logger.error(f"Error generating compliance report PDF: {str(e)}")
            raise
    
    @staticmethod
    def generate_analytics_dashboard_pdf(dashboard_data):
        """
        Generate PDF for analytics dashboard.
        
        Args:
            dashboard_data: Dictionary with dashboard metrics and charts
            
        Returns:
            BytesIO: PDF file as bytes
        """
        try:
            context = {
                'dashboard_data': dashboard_data,
                'current_date': timezone.now(),
                'portal_name': 'Enwealth Governance Portal',
            }
            
            html_content = render_to_string('documents/pdf/analytics_dashboard_pdf.html', context)
            
            css_content = render_to_string('documents/pdf/pdf_styles.css')
            css = CSS(string=css_content)
            
            html = HTML(string=html_content, base_url='')
            pdf_file = html.write_pdf(stylesheets=[css])
            
            return BytesIO(pdf_file)
            
        except Exception as e:
            logger.error(f"Error generating analytics dashboard PDF: {str(e)}")
            raise
    
    @staticmethod
    def generate_custom_report_pdf(title, content_data, template_name=None):
        """
        Generate PDF from custom template.
        
        Args:
            title: Report title
            content_data: Dictionary with report content
            template_name: Optional custom template name
            
        Returns:
            BytesIO: PDF file as bytes
        """
        try:
            context = {
                'title': title,
                'content': content_data,
                'current_date': timezone.now(),
                'portal_name': 'Enwealth Governance Portal',
            }
            
            if template_name:
                html_content = render_to_string(f'documents/pdf/{template_name}.html', context)
            else:
                html_content = render_to_string('documents/pdf/custom_report_pdf.html', context)
            
            css_content = render_to_string('documents/pdf/pdf_styles.css')
            css = CSS(string=css_content)
            
            html = HTML(string=html_content, base_url='')
            pdf_file = html.write_pdf(stylesheets=[css])
            
            return BytesIO(pdf_file)
            
        except Exception as e:
            logger.error(f"Error generating custom report PDF: {str(e)}")
            raise
