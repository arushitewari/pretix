from unittest.mock import MagicMock
from pretix.base.models.event_defaults_strategies import (
    InvoiceDefaultsStrategy,
    TicketOutputDefaultsStrategy,
    DisplayDefaultsStrategy,
)

def test_invoice_defaults():
    event = MagicMock()
    InvoiceDefaultsStrategy().apply(event)
    event.settings.__setattr__.assert_any_call('invoice_renderer', 'modern1')

def test_ticket_defaults():
    event = MagicMock()
    TicketOutputDefaultsStrategy().apply(event)
    event.settings.__setattr__.assert_any_call('ticketoutput_pdf__enabled', True)

def test_display_defaults():
    event = MagicMock()
    DisplayDefaultsStrategy().apply(event)
    event.settings.__setattr__.assert_any_call('name_scheme', 'given_family')
