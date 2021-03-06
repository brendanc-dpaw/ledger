import datetime

from dateutil.parser import parse as date_parse
from django.contrib.staticfiles.templatetags.staticfiles import static
from django.core.urlresolvers import reverse_lazy, reverse
from django.db.models import Q
from django.http.response import HttpResponse

from wildlifelicensing.apps.applications.models import Application
from wildlifelicensing.apps.dashboard.views import base
from wildlifelicensing.apps.dashboard.views.customer import DataTableReturnsCustomerView
from wildlifelicensing.apps.main.helpers import get_all_officers
from wildlifelicensing.apps.main.mixins import OfficerRequiredMixin
from wildlifelicensing.apps.main.models import WildlifeLicence
from wildlifelicensing.apps.main.pdf import bulk_licence_renewal_pdf_bytes
from wildlifelicensing.apps.returns.models import Return
from wildlifelicensing.apps.returns.utils import is_return_overdue, is_return_due_soon


def _render_cover_letter_document(licence):
    if licence is not None and licence.cover_letter_document is not None:
        return '<a href="{0}" target="_blank">View PDF</a><img height="20" src="{1}"></img>'.format(
            licence.cover_letter_document.file.url, static('wl/img/pdf.png'))
    else:
        return ''


class DashboardOfficerTreeView(OfficerRequiredMixin, base.DashboardTreeViewBase):
    template_name = 'wl/dash_tree.html'
    title = 'Officer Dashboard'

    def _build_tree_nodes(self):
        # Applications
        # The draft status is excluded from the officer status list
        url = reverse_lazy('wl_dashboard:tables_applications_officer')
        result = []
        statuses = base.get_processing_statuses_but_draft()
        all_applications = Application.objects.filter(processing_status__in=[s[0] for s in statuses])
        all_applications_node = self._create_node('All applications', href=url,
                                                  count=all_applications.count())
        all_applications_node['state']['expanded'] = False
        for s_value, s_title in statuses:
            applications = all_applications.filter(processing_status=s_value)
            if applications.count() > 0:
                query = {
                    'application_status': s_value,
                }
                href = base.build_url(url, query)
                node = self._create_node(s_title, href=href, count=applications.count())
                self._add_node(all_applications_node, node)

        assigned_applications = all_applications.filter(assigned_officer=self.request.user)
        query = {
            'application_assignee': self.request.user.pk
        }
        assigned_applications_node = self._create_node('My assigned applications',
                                                       href=base.build_url(url, query),
                                                       count=assigned_applications.count())
        assigned_applications_node['state']['expanded'] = True
        for s_value, s_title in statuses:
            applications = assigned_applications.filter(processing_status=s_value)
            if applications.count() > 0:
                query.update({
                    'application_status': s_value
                })
                href = base.build_url(url, query)
                node = self._create_node(s_title, href=href, count=applications.count())
                self._add_node(assigned_applications_node, node)
        result.append(assigned_applications_node)

        on_behalf_pending_applications_count = \
            DataTableApplicationsOfficerOnBehalfView._get_proxy_applications(self.request.user).filter(
                DataTableApplicationsOfficerOnBehalfView.filter_status(
                    TableApplicationsOfficerView.STATUS_PENDING)).count()

        on_behalf_overdue_returns_count = DataTableReturnsOfficerOnBehalfView._get_proxy_returns(
            self.request.user).filter(
            DataTableReturnsOfficerOnBehalfView.filter_status(TableReturnsOfficerView.OVERDUE_FILTER)).count()

        total_on_behalf = on_behalf_pending_applications_count + on_behalf_overdue_returns_count
        if total_on_behalf > 0:
            url = reverse_lazy('wl_dashboard:tables_officer_onbehalf')
            on_behalf_node = self._create_node('My proxy page', href=url, count=total_on_behalf)
            query = {
                'show': 'applications',
                'application_status': 'pending'
            }
            href = base.build_url(url, query)
            on_behalf_applications_node = self._create_node('Pending Applications',
                                                            href=href,
                                                            count=on_behalf_pending_applications_count)

            query = {
                'show': 'returns',
            }
            href = base.build_url(url, query)
            on_behalf_returns_node = self._create_node('Overdue Returns',
                                                       href=href,
                                                       count=on_behalf_overdue_returns_count)
            self._add_node(on_behalf_node, on_behalf_applications_node)
            self._add_node(on_behalf_node, on_behalf_returns_node)
            on_behalf_node['state']['expanded'] = False
            result.append(on_behalf_node)

        result.append(all_applications_node)

        # Licences
        url = reverse_lazy('wl_dashboard:tables_licences_officer')
        all_licences_node = self._create_node('All licences', href=url, count=WildlifeLicence.objects.count())
        result.append(all_licences_node)

        # Returns
        url = reverse_lazy('wl_dashboard:tables_returns_officer')
        all_returns_node = self._create_node('All returns', href=url,
                                             count=Return.objects.exclude(status__in=['draft', 'future']).count())
        result.append(all_returns_node)

        return result


class TableApplicationsOfficerView(OfficerRequiredMixin, base.TableBaseView):
    template_name = 'wl/dash_tables_applications_officer.html'

    STATUS_PENDING = 'pending'

    def _build_data(self):
        data = super(TableApplicationsOfficerView, self)._build_data()
        data['applications']['columnDefinitions'] = [
            {
                'title': 'Lodge Number'
            },
            {
                'title': 'Licence Type'
            },
            {
                'title': 'User'
            },
            {
                'title': 'Status',
            },
            {
                'title': 'Lodged on'
            },
            {
                'title': 'Assignee'
            },
            {
                'title': 'Proxy'
            },
            {
                'title': 'Payment',
                'searchable': False,
                'orderable': False
            },
            {
                'title': 'Action',
                'searchable': False,
                'orderable': False
            }
        ]
        data['applications']['filters']['status']['values'] = \
            [('all', 'All')] + [(self.STATUS_PENDING, self.STATUS_PENDING.capitalize())] + \
            base.get_processing_statuses_but_draft()
        data['applications']['filters']['assignee'] = {
            'values': [('all', 'All')] + [(user.pk, base.render_user_name(user),) for user in get_all_officers()]
        }
        data['applications']['ajax']['url'] = reverse('wl_dashboard:data_application_officer')
        # global table options
        data['applications']['tableOptions'] = {
            'pageLength': 25
        }
        return data


class DataTableApplicationsOfficerView(OfficerRequiredMixin, base.DataTableApplicationBaseView):
    columns = [
        'lodgement_number',
        'licence_type',
        'applicant',
        'processing_status',
        'lodgement_date',
        'assigned_officer',
        'proxy_applicant',
        'payment',
        'action'
    ]
    order_columns = [
        'lodgement_number',
        ['licence_type.short_name', 'licence_type.name'],
        ['applicant.last_name', 'applicant.first_name', 'applicant.email'],
        'processing_status',
        'lodgement_date',
        ['assigned_officer.first_name', 'assigned_officer.last_name', 'assigned_officer.email'],
        ['proxy_applicant.first_name', 'proxy_applicant.last_name', 'proxy_applicant.email'],
        ''
        ''
    ]

    columns_helpers = dict(base.DataTableApplicationBaseView.columns_helpers.items(), **{
        'lodgement_number': {
            'search': lambda self, search: DataTableApplicationsOfficerView._search_lodgement_number(search),
            'render': lambda self, instance: base.render_lodgement_number(instance),
        },
        'assigned_officer': {
            'search': lambda self, search: base.build_field_query(
                ['assigned_officer__last_name', 'assigned_officer__first_name'],
                search
            ),
            'render': lambda self, instance: base.render_user_name(instance.assigned_officer)
        },
        'proxy_applicant': {
            'search': lambda self, search: base.build_field_query([
                'proxy_applicant__last_name', 'proxy_applicant__first_name'],
                search),
            'render': lambda self, obj: base.render_user_name(obj.proxy_applicant)
        },
        'action': {
            'render': lambda self, instance: DataTableApplicationsOfficerView._render_action_column(instance),
        },
        'lodgement_date': {
            'render': lambda self, instance: base.render_date(instance.lodgement_date)
        },
        'payment': {
            'render': lambda self, instance: base.render_payment(instance, self.request.build_absolute_uri(
                reverse('wl_dashboard:tables_applications_officer')))
        },
    })

    @staticmethod
    def _get_pending_processing_statuses():
        return [s[0] for s in Application.PROCESSING_STATUS_CHOICES
                if s[0] != 'draft' and s[0] != 'issued' and s[0] != 'declined']

    @staticmethod
    def filter_status(value):
        # officers should not see applications in draft mode.
        if value.lower() == TableApplicationsOfficerView.STATUS_PENDING:
            return Q(processing_status__in=DataTableApplicationsOfficerView._get_pending_processing_statuses())
        return Q(processing_status=value) if value != 'all' else ~Q(customer_status='draft')

    @staticmethod
    def _search_lodgement_number(search):
        # testing to see if search term contains no spaces and two hyphens, meaning it's a lodgement number with a sequence
        if search and search.count(' ') == 0 and search.count('-') == 2:
            components = search.split('-')
            lodgement_number, lodgement_sequence = '-'.join(components[:2]), '-'.join(components[2:])

            return Q(lodgement_number__icontains=lodgement_number) & Q(lodgement_sequence__icontains=lodgement_sequence)
        else:
            return Q(lodgement_number__icontains=search)

    @staticmethod
    def _render_action_column(obj):
        if obj.processing_status == 'ready_for_conditions':
            return '<a href="{0}">Enter Conditions</a>'.format(
                reverse('wl_applications:enter_conditions', args=[obj.pk]),
            )
        if obj.processing_status == 'ready_to_issue':
            return '<a href="{0}">Issue Licence</a>'.format(
                reverse('wl_applications:issue_licence', args=[obj.pk]),
            )
        elif obj.processing_status == 'issued' and obj.licence is not None and obj.licence.licence_document is not None:
            return '<a href="{0}">{1}</a>'.format(
                reverse('wl_applications:view_application_officer', args=[obj.pk]),
                'View application (read-only)'
            )
        else:
            return '<a href="{0}">Process</a>'.format(
                reverse('wl_applications:process', args=[obj.pk]),
            )

    def get_initial_queryset(self):
        return Application.objects.exclude(processing_status__in=['draft', 'temp'])


class TablesOfficerOnBehalfView(OfficerRequiredMixin, base.TableBaseView):
    template_name = 'wl/dash_tables_officer_onbehalf.html'

    def _build_data(self):
        data = super(TablesOfficerOnBehalfView, self)._build_data()
        officer_data = TableApplicationsOfficerView()._build_data()
        data['applications'] = officer_data['applications']
        data['applications']['columnDefinitions'] = [
            {
                'title': 'Lodge Number'
            },
            {
                'title': 'Licence Type'
            },
            {
                'title': 'User'
            },
            {
                'title': 'Status'
            },
            {
                'title': 'Lodged on'
            },
            {
                'title': 'Action',
                'searchable': False,
                'orderable': False
            }
        ]
        data['applications']['ajax']['url'] = reverse('wl_dashboard:data_application_officer_onbehalf')
        data['applications']['filters']['status']['values'] = \
            [(TableApplicationsOfficerView.STATUS_PENDING, TableApplicationsOfficerView.STATUS_PENDING.capitalize())] + \
            [('all', 'All')] + \
            [s for s in Application.PROCESSING_STATUS_CHOICES]

        # returns
        officer_data = TableReturnsOfficerView()._build_data()
        data['returns'] = officer_data['returns']
        # override the url
        data['returns']['ajax']['url'] = reverse('wl_dashboard:data_returns_officer_onbehalf')
        # and the filters (proxy officer should see the drafts)
        filters = {
            'status': {
                'values': [
                              (TableReturnsOfficerView.OVERDUE_FILTER,
                               TableReturnsOfficerView.OVERDUE_FILTER.capitalize())
                          ] + [('all', 'All')] + list(Return.STATUS_CHOICES)
            }
        }
        data['returns']['filters'].update(filters)

        return data


class DataTableApplicationsOfficerOnBehalfView(OfficerRequiredMixin, base.DataTableApplicationBaseView):
    columns = [
        'lodgement_number',
        'licence_type',
        'applicant',
        'processing_status',
        'lodgement_date',
        'action'
    ]
    order_columns = [
        'lodgement_number',
        ['licence_type.short_name', 'licence_type.name'],
        ['applicant.last_name', 'applicant.first_name', 'applicant.email'],
        'processing_status',
        'lodgement_date',
        '']

    columns_helpers = dict(base.DataTableApplicationBaseView.columns_helpers.items(), **{
        'lodgement_number': {
            'render': lambda self, instance: base.render_lodgement_number(instance)
        },
        'lodgement_date': {
            'render': lambda self, instance: base.render_date(instance.lodgement_date)
        },
        'action': {
            'render': lambda self, instance: self._render_action_column(instance),
        },
    })

    @staticmethod
    def _get_pending_processing_statuses():
        return [s[0] for s in Application.PROCESSING_STATUS_CHOICES
                if s[0] != 'issued' and s[0] != 'declined' and s[0] != 'temp']

    @staticmethod
    def _render_action_column(obj):
        status = obj.customer_status
        if status == 'draft':
            return '<a href="{0}">{1}</a> / <a href="{2}">{3}</a>'.format(
                reverse('wl_applications:edit_application', args=[obj.pk]),
                'Continue',
                reverse('wl_applications:delete_application', args=[obj.pk]),
                'Discard'
            )
        elif status == 'amendment_required' or status == 'id_and_amendment_required':
            return '<a href="{0}">{1}</a>'.format(
                reverse('wl_applications:edit_application', args=[obj.pk]),
                'Amend application'
            )
        elif status == 'id_required' and obj.id_check_status == 'awaiting_update':
            return '<a href="{0}">{1}</a>'.format(
                reverse('wl_main:identification'),
                'Update ID')
        else:
            return '<a href="{0}">{1}</a>'.format(
                reverse('wl_applications:view_application', args=[obj.pk]),
                'View application (read-only)'
            )

    @staticmethod
    def _get_proxy_applications(user):
        return Application.objects.filter(proxy_applicant=user)

    @staticmethod
    def filter_status(value):
        if value.lower() == TableApplicationsOfficerView.STATUS_PENDING:
            return Q(processing_status__in=DataTableApplicationsOfficerOnBehalfView._get_pending_processing_statuses())
        else:
            return base.DataTableApplicationBaseView.filter_status(value)

    def get_initial_queryset(self):
        return self._get_proxy_applications(self.request.user)


class TableLicencesOfficerView(OfficerRequiredMixin, base.TableBaseView):
    template_name = 'wl/dash_tables_licences_officer.html'

    STATUS_FILTER_ACTIVE = 'active'
    STATUS_FILTER_RENEWABLE = 'renewable'
    STATUS_FILTER_EXPIRED = 'expired'
    STATUS_FILTER_ALL = 'all'

    def _build_data(self):
        data = super(TableLicencesOfficerView, self)._build_data()
        del data['applications']
        del data['returns']
        data['licences']['columnDefinitions'] = [
            {
                'title': 'Licence Number'
            },
            {
                'title': 'Licence Type'
            },
            {
                'title': 'User'
            },
            {
                'title': 'Start Date'
            },
            {
                'title': 'Expiry Date'
            },
            {
                'title': 'Licence PDF',
                'searchable': False,
                'orderable': False
            },
            {
                'title': 'Cover Letter',
                'searchable': False,
                'orderable': False
            },
            {
                'title': 'Renewal Letter',
                'searchable': False,
                'orderable': False
            },
            {
                'title': 'Action',
                'searchable': False,
                'orderable': False
            }
        ]
        data['licences']['ajax']['url'] = reverse('wl_dashboard:data_licences_officer')
        # filters (note: there is already the licenceType from the super class)
        filters = {
            'status': {
                'values': [
                    (self.STATUS_FILTER_ALL, self.STATUS_FILTER_ALL.capitalize()),
                    (self.STATUS_FILTER_ACTIVE, self.STATUS_FILTER_ACTIVE.capitalize()),
                    (self.STATUS_FILTER_RENEWABLE,
                     self.STATUS_FILTER_RENEWABLE.capitalize() + ' (expires within 30 days)'),
                    (self.STATUS_FILTER_EXPIRED, self.STATUS_FILTER_EXPIRED.capitalize()),
                ]
            }
        }
        data['licences']['filters'].update(filters)
        # global table options
        data['licences']['tableOptions'] = {
            'pageLength': 25
        }
        # other stuff
        data['licences']['bulkRenewalURL'] = reverse('wl_dashboard:bulk_licence_renewal_pdf')
        return data


class DataTableLicencesOfficerView(OfficerRequiredMixin, base.DataTableBaseView):
    model = WildlifeLicence
    columns = [
        'licence_number',
        'licence_type',
        'profile.user',
        'start_date',
        'end_date',
        'licence',
        'cover_letter',
        'renewal_letter',
        'action']
    order_columns = [
        'licence_number',
        ['licence_type.short_name', 'licence_type.name'],
        ['profile.user.last_name', 'profile.user.first_name'],
        'start_date',
        'end_date',
        '',
        '']

    columns_helpers = dict(base.DataTableBaseView.columns_helpers.items(), **{
        'licence_number': {
            'search': lambda self, search: DataTableLicencesOfficerView._search_licence_number(search),
            'render': lambda self, instance: base.render_licence_number(instance)
        },
        'profile.user': {
            'render': lambda self, instance: base.render_user_name(instance.profile.user, first_name_first=False),
            'search': lambda self, search: base.build_field_query([
                'profile__user__last_name', 'profile__user__first_name'],
                search),
        },
        'issue_date': {
            'render': lambda self, instance: base.render_date(instance.issue_date)
        },
        'start_date': {
            'render': lambda self, instance: base.render_date(instance.start_date)
        },
        'end_date': {
            'render': lambda self, instance: base.render_date(instance.end_date)
        },
        'licence': {
            'render': lambda self, instance: base.render_licence_document(instance)
        },
        'cover_letter': {
            'render': lambda self, instance: _render_cover_letter_document(instance)
        },
        'renewal_letter': {
            'render': lambda self, instance: self._render_renewal_letter(instance)
        },
        'action': {
            'render': lambda self, instance: self._render_action(instance)
        }
    })

    @staticmethod
    def filter_status(value):
        today = datetime.date.today()
        if value == TableLicencesOfficerView.STATUS_FILTER_ACTIVE:
            return Q(start_date__lte=today) & Q(end_date__gte=today)
        elif value == TableLicencesOfficerView.STATUS_FILTER_RENEWABLE:
            return Q(is_renewable=True) & Q(end_date__gte=today) & Q(end_date__lte=today + datetime.timedelta(days=30))
        elif value == TableLicencesOfficerView.STATUS_FILTER_EXPIRED:
            return Q(end_date__lt=today)
        else:
            return None

    @staticmethod
    def filter_licence_type(value):
        if value.lower() != 'all':
            return Q(licence_type__pk=value)
        else:
            return None

    @staticmethod
    def filter_expiry_after(value):
        if value:
            try:
                date = date_parse(value, dayfirst=True).date()
                return Q(end_date__gte=date)
            except:
                pass
        return None

    @staticmethod
    def filter_expiry_before(value):
        if value:
            try:
                date = date_parse(value, dayfirst=True).date()
                return Q(end_date__lte=date)
            except:
                pass
        return None

    @staticmethod
    def _search_licence_number(search):
        # testing to see if search term contains no spaces and two hyphens, meaning it's a lodgement number with a sequence
        if search and search.count(' ') == 0 and search.count('-') == 2:
            components = search.split('-')
            licence_number, licence_sequence = '-'.join(components[:2]), '-'.join(components[2:])

            return Q(licence_number__icontains=licence_number) & Q(licence_sequence__icontains=licence_sequence)
        else:
            return Q(licence_number__icontains=search)

    @staticmethod
    def _render_renewal_letter(instance):
        if instance.is_renewable:
            return '<a href="{0}" target="_blank">Create PDF</a><img height="20" src="{1}"></img>'. \
                format(reverse('wl_main:licence_renewal_pdf', args=(instance.pk,)), static('wl/img/pdf.png'))
        else:
            return 'Not renewable'

    @staticmethod
    def _render_action(instance):
        reissue_url = reverse('wl_applications:reissue_licence', args=(instance.pk,))
        expiry_days = (instance.end_date - datetime.date.today()).days

        if expiry_days <= 30 and instance.is_renewable:
            renew_url = reverse('wl_applications:renew_licence', args=(instance.pk,))
            return '<a href="{0}">Renew</a> / <a href="{1}">Reissue</a>'.format(renew_url, reissue_url)
        else:
            amend_url = reverse('wl_applications:amend_licence', args=(instance.pk,))
            return '<a href="{0}">Amend</a> / <a href="{1}">Reissue</a>'.format(amend_url, reissue_url)

    def get_initial_queryset(self):
        return WildlifeLicence.objects.all()


class TableReturnsOfficerView(OfficerRequiredMixin, base.TableBaseView):
    template_name = 'wl/dash_tables_returns_officer.html'

    STATUS_FILTER_ALL_BUT_DRAFT_OR_FUTURE = 'all_but_draft_or_future'
    OVERDUE_FILTER = 'overdue'

    def _build_data(self):
        data = super(TableReturnsOfficerView, self)._build_data()
        del data['applications']
        del data['licences']
        data['returns']['columnDefinitions'] = [
            {
                'title': 'Lodge Number'
            },
            {
                'title': 'Licence Type'
            },
            {
                'title': 'User'
            },
            {
                'title': 'Lodged On'
            },
            {
                'title': 'Due On'
            },
            {
                'title': 'Status'
            },
            {
                'title': 'Licence',
                'orderable': False
            },
            {
                'title': 'Action',
                'searchable': False,
                'orderable': False
            }
        ]
        data['returns']['ajax']['url'] = reverse('wl_dashboard:data_returns_officer')
        # global table options
        data['returns']['tableOptions'] = {
            'pageLength': 25
        }
        filters = {
            'status': {
                'values': [
                              (self.STATUS_FILTER_ALL_BUT_DRAFT_OR_FUTURE, 'All (but draft or future)'),
                              (self.OVERDUE_FILTER, self.OVERDUE_FILTER.capitalize())
                          ] + list(Return.STATUS_CHOICES)
            }
        }
        data['returns']['filters'].update(filters)

        return data


class DataTableReturnsOfficerView(base.DataTableBaseView):
    model = Return
    columns = [
        'lodgement_number',
        'licence.licence_type',
        'licence.profile.user',
        'lodgement_date',
        'due_date',
        'status',
        'licence_number',
        'action',
    ]
    order_columns = [
        'lodgement_number',
        'licence.licence_type',
        ['licence.profile.user.last_name', 'licence.profile.user.first_name'],
        'lodgement_date',
        'due_date',
        'status',
        '',
        '']
    columns_helpers = dict(base.DataTableBaseView.columns_helpers.items(), **{
        'licence.licence_type': {
            'render': lambda self, instance: instance.licence.licence_type.display_name,
            'search': lambda self, search: base.build_field_query(
                ['licence__licence_type__short_name', 'licence__licence_type__name', 'licence__licence_type__version'],
                search)
        },
        'lodgement_number': {
            'render': lambda self, instance: instance.lodgement_number
        },
        'lodgement_date': {
            'render': lambda self, instance: base.render_date(instance.lodgement_date)
        },
        'licence.profile.user': {
            'render': lambda self, instance: base.render_user_name(instance.licence.profile.user,
                                                                   first_name_first=False),
            'search': lambda self, search: base.build_field_query([
                'licence__profile__user__last_name', 'licence__profile__user__first_name'],
                search),
        },
        'due_date': {
            'render': lambda self, instance: base.render_date(instance.due_date)
        },
        'status': {
            'render': lambda self, instance: self._render_status(instance)
        },
        'licence_number': {
            'render': lambda self, instance: base.render_licence_number(instance.licence),
            'search': lambda self, search: DataTableReturnsOfficerView._search_licence_number(search),

        },
        'action': {
            'render': lambda self, instance: self._render_action(instance)
        }
    })

    @staticmethod
    def _render_status(instance):
        status = instance.status
        if status == 'current':
            if is_return_overdue(instance):
                return '<span class="label label-danger">Overdue</span>'
            elif is_return_due_soon(instance):
                return '<span class="label label-warning">Due soon</span>'
            else:
                return 'Current'
        else:
            return dict(Return.STATUS_CHOICES)[status]

    @staticmethod
    def _render_action(instance):
        if instance.status == 'current' or instance.status == 'future':
            url = reverse('wl_returns:enter_return', args=(instance.pk,))
            return '<a href="{0}">Enter Return</a>'.format(url)
        elif instance.status == 'draft':
            url = reverse('wl_returns:enter_return', args=(instance.pk,))
            return '<a href="{0}">Edit Return</a>'.format(url)
        elif instance.status == 'submitted':
            text = 'Curate Return'
            if instance.nil_return:
                text = 'Nil Return'
            url = reverse('wl_returns:curate_return', args=(instance.pk,))
            return '<a href="{0}">{1}</a>'.format(url, text)
        else:
            url = reverse('wl_returns:view_return', args=(instance.pk,))
            return '<a href="{0}">View Return (read-only)</a>'.format(url)

    @staticmethod
    def filter_licence_type(value):
        if value.lower() != 'all':
            return Q(return_type__licence_type__pk=value)
        else:
            return None

    @staticmethod
    def filter_status(value):
        if value == TableReturnsOfficerView.STATUS_FILTER_ALL_BUT_DRAFT_OR_FUTURE:
            return ~Q(status__in=['draft', 'future'])
        elif value == TableReturnsOfficerView.OVERDUE_FILTER:
            return Q(due_date__lt=datetime.date.today()) & ~Q(
                status__in=['future', 'submitted', 'accepted', 'declined'])
        elif value == 'all':
            return None
        else:
            return Q(status=value)

    @staticmethod
    def _search_licence_number(search):
        # testing to see if search term contains no spaces and two hyphens, meaning it's a lodgement number with a sequence
        if search and search.count(' ') == 0 and search.count('-') == 2:
            components = search.split('-')
            licence_number, licence_sequence = '-'.join(components[:2]), '-'.join(components[2:])

            return Q(licence__licence_number__icontains=licence_number) & Q(
                licence__licence_sequence__icontains=licence_sequence)
        else:
            return Q(licence__licence_number__icontains=search)

    def get_initial_queryset(self):
        return Return.objects.all()


class DataTableReturnsOfficerOnBehalfView(DataTableReturnsOfficerView):
    @staticmethod
    def _render_action(instance):
        # same actions as a customer
        return DataTableReturnsCustomerView._render_action(instance)

    @staticmethod
    def _get_proxy_returns(user):
        return Return.objects.filter(
            licence__in=WildlifeLicence.objects.filter(application__proxy_applicant=user))

    def get_initial_queryset(self):
        return self._get_proxy_returns(self.request.user)


class BulkLicenceRenewalPDFView(DataTableLicencesOfficerView):
    def filter_queryset(self, qs):
        qs = super(BulkLicenceRenewalPDFView, self).filter_queryset(qs)
        self.qs = qs
        return qs

    def get(self, request, *args, **kwargs):
        super(BulkLicenceRenewalPDFView, self).get(request, *args, **kwargs)
        licences = []
        if self.qs:
            licences = self.qs
        response = HttpResponse(content_type='application/pdf')
        response.write(bulk_licence_renewal_pdf_bytes(licences, request.build_absolute_uri(reverse('home'))))
        return response
