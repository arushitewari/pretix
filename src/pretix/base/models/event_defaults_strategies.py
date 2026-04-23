class EventDefaultsStrategy:
    def apply(self, event):
        raise NotImplementedError


class InvoiceDefaultsStrategy(EventDefaultsStrategy):
    def apply(self, event):
        event.settings.invoice_renderer = 'modern1'
        event.settings.invoice_include_expire_date = True
        event.settings.invoice_renderer_highlight_order_code = True
        event.settings.invoice_email_attachment = True


class TicketOutputDefaultsStrategy(EventDefaultsStrategy):
    def apply(self, event):
        event.settings.ticketoutput_pdf__enabled = True
        event.settings.ticketoutput_passbook__enabled = True


class DisplayDefaultsStrategy(EventDefaultsStrategy):
    def apply(self, event):
        event.settings.event_list_type = 'calendar'
        event.settings.name_scheme = 'given_family'
        event.settings.low_availability_percentage = 10


class PaymentDefaultsStrategy(EventDefaultsStrategy):
    def apply(self, event):
        event.settings.payment_banktransfer_invoice_immediately = True
