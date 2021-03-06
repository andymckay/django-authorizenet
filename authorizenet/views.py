from django.shortcuts import render_to_response
from django.template import RequestContext
from authorizenet.models import Response
from authorizenet.forms import AIMPaymentForm, BillingAddressForm
from django.http import HttpResponseRedirect
from authorizenet.signals import payment_was_successful, payment_was_flagged

def sim_payment(request):
    response = Response.objects.create_from_dict(request.POST)
    if response.is_approved:
        payment_was_successful.send(sender=response)
    else:
        payment_was_flagged.send(sender=response)
    return render_to_response('authorizenet/sim_payment.html', context_instance=RequestContext(request))

class AIMPayment(object):
    """
    Class to handle credit card payments to Authorize.NET
    """

    processing_error = "There was an error processing your payment. Check your information and try again."
    form_error = "Please correct the errors below and try again."

    def __init__(self, extra_data=None, payment_form_class=AIMPaymentForm, context=None, billing_form_class=BillingAddressForm, payment_template="authorizenet/aim_payment.html", success_template='authorizenet/aim_success.html', initial_data={}):
        self.extra_data = extra_data
        self.payment_form_class = payment_form_class
        self.payment_template = payment_template
        self.success_template = success_template
        self.context = context
        self.initial_data = initial_data
        self.billing_form_class = billing_form_class

    def __call__(self, request):
        self.request = request
        if request.method == "GET":
            return self.render_payment_form()
        else:
            return self.validate_payment_form()

    def render_payment_form(self):
        self.context['payment_form'] = self.payment_form_class(initial=self.initial_data)
        self.context['billing_form'] = self.billing_form_class(initial=self.initial_data)
        return render_to_response(self.payment_template, self.context, context_instance=RequestContext(self.request))

    def validate_payment_form(self):
        payment_form = self.payment_form_class(self.request.POST)
        billing_form = self.billing_form_class(self.request.POST)
        if payment_form.is_valid() and billing_form.is_valid():
            from authorizenet.utils import process_payment, combine_form_data
            form_data = combine_form_data(payment_form, billing_form)
            response = process_payment(form_data, self.extra_data)
            self.context['response'] = response
            if response.is_approved:
                return render_to_response(self.success_template, self.context, context_instance=RequestContext(self.request))
            else:
                self.context['errors'] = self.processing_error
        self.context['payment_form'] = payment_form
        self.context['billing_form'] = billing_form
        self.context.setdefault('errors', self.form_error)
        return render_to_response(self.payment_template, self.context, context_instance=RequestContext(self.request))


