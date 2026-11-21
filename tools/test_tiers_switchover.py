"""Migration guards must preserve backend access and active roles."""
import unittest

from tiers_switchover import candidates


class AccountRpc:
    def __init__(self, groups=None, roles=0, allowed=True):
        self.groups = [10] if groups is None else groups
        self.roles, self.allowed = roles, allowed

    def ref(self, name):
        return {'base.group_user': 10, 'base.group_multi_company': 11,
                'pb_driver_checkin.group_pb_driver': 12,
                'pb_driver_checkin.group_pb_field_staff': 13}.get(name)

    def call(self, model, method, *args, **kw):
        if model == 'res.groups':
            return [{'all_implied_ids': [20]}]
        if method == 'people':
            return [{'id': 100, 'login': 'employee@example.invalid',
                     'name': 'DEMO Employee', 'kind': 'staff', 'has_employee': True}]
        if model == 'res.users':
            return [{'group_ids': self.groups, 'share': False}]
        if method == 'passport':
            return {'header': {'switch': {'to': 'employee', 'allowed': self.allowed,
                                         'roles_ending': self.roles}}}
        raise AssertionError((model, method))


class MigrationGuardTests(unittest.TestCase):
    def test_plain_employee_and_multicompany_can_be_converted(self):
        for groups in ([10], [10, 20], [10, 11]):
            with self.subTest(groups=groups):
                self.assertEqual(len(candidates(AccountRpc(groups), verbose=False)), 1)

    def test_driver_field_and_hand_given_permissions_are_preserved(self):
        for gid in (12, 13, 99):
            with self.subTest(gid=gid):
                self.assertEqual(candidates(AccountRpc([10, gid]), verbose=False), [])

    def test_active_roles_are_preserved_even_when_the_switch_would_allow_it(self):
        self.assertEqual(candidates(AccountRpc(roles=1), verbose=False), [])

    def test_business_switch_refusal_is_authoritative(self):
        self.assertEqual(candidates(AccountRpc(allowed=False), verbose=False), [])


if __name__ == '__main__':
    unittest.main()
