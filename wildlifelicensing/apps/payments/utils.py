import json

from django.shortcuts import get_object_or_404

from oscar.apps.partner.strategy import Selector
from oscar.apps.voucher.models import Voucher

from ledger.catalogue.models import Product
from ledger.payments.invoice.models import Invoice

from wildlifelicensing.apps.main.serializers import WildlifeLicensingJSONEncoder


PAYMENT_STATUS_PAID = 'paid'
PAYMENT_STATUS_CC_READY = 'cc_ready'
PAYMENT_STATUS_AWAITING = 'awaiting'
PAYMENT_STATUS_NOT_REQUIRED = 'not_required'

PAYMENT_STATUSES = {
    PAYMENT_STATUS_PAID: 'Paid',
    PAYMENT_STATUS_CC_READY: 'Credit Card Ready',
    PAYMENT_STATUS_AWAITING: 'Awaiting Payment',
    PAYMENT_STATUS_NOT_REQUIRED: 'Payment Not Required',
}


def to_json(data):
    return json.dumps(data, cls=WildlifeLicensingJSONEncoder)


def generate_product_code_variants(licence_type):
    def __append_variant_codes(product_code, variant_group, current_variant_codes):
        if variant_group is None:
            variant_codes.append(product_code)
            return

        for variant in variant_group.variants.all():
            variant_code = '{}_{}'.format(product_code, variant.product_code)

            __append_variant_codes(variant_code, variant_group.child, variant_codes)

    variant_codes = []

    __append_variant_codes(licence_type.product_code, licence_type.variant_group, variant_codes)

    return variant_codes


def generate_product_code(application):
    product_code = application.licence_type.product_code

    if application.variants.exists():
        product_code += '_' + '_'.join(application.variants.through.objects.filter(application=application).
                                       order_by('order').values_list('variant__product_code', flat=True))

    return product_code


def get_product(product_code):
    try:
        return Product.objects.get(title=product_code)
    except Product.DoesNotExist:
        return None


def is_licence_free(product_code):
    product = get_product(product_code)

    if product is None:
        return True

    selector = Selector()
    strategy = selector.strategy()
    purchase_info = strategy.fetch_for_product(product=product)

    return purchase_info.price.effective_price == 0


def get_application_payment_status(application):
    """
    :param application:
    :return: One of PAYMENT_STATUS_PAID, PAYMENT_STATUS_CC_READY, PAYMENT_STATUS_AWAITING or PAYMENT_STATUS_NOT_REQUIRED
    """
    if not application.invoice_reference:
        return PAYMENT_STATUS_NOT_REQUIRED

    invoice = get_object_or_404(Invoice, reference=application.invoice_reference)

    if invoice.amount > 0:
        payment_status = invoice.payment_status

        if payment_status == 'paid' or payment_status == 'over_paid':
            return PAYMENT_STATUS_PAID
        elif invoice.token:
            return PAYMENT_STATUS_CC_READY
        else:
            return PAYMENT_STATUS_AWAITING
    else:
        return PAYMENT_STATUS_NOT_REQUIRED


def invoke_credit_card_payment(application):
    invoice = get_object_or_404(Invoice, reference=application.invoice_reference)

    if not invoice.token:
        raise Exception('Application invoice does have a credit payment token')

    invoice.make_payment()


def get_voucher(voucher_code):
    return Voucher.objects.filter(code=voucher_code).first()
