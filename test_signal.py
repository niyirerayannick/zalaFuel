import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aflms.settings.development')
django.setup()

from accounts.models import User
from transport.drivers.models import Driver
from transport.customers.models import Customer

# Clean all existing test data first
Driver.objects.filter(license_number__startswith='PENDING-').delete()
Driver.objects.filter(email__endswith='@test.com').delete()
Customer.objects.filter(email__endswith='@test.com').delete()
for c in Customer.objects.all():
    if c.user and c.user.role == 'driver':
        c.delete()

results = []

# TEST 1: Create user with role=driver from admin (one-shot)
print("=== Test 1: Admin creates user with role=driver ===")
u1 = User.objects.create_user(
    email='t1_driver@test.com', full_name='T1 Driver', password='p',
    role='driver', phone='+250780000001'
)
d1 = Driver.objects.filter(user=u1).count()
c1 = Customer.objects.filter(user=u1).count()
print(f"  Drivers: {d1} (expect 1) | Customers: {c1} (expect 0)")
results.append(d1 == 1 and c1 == 0)

# TEST 2: Create user with role=client from admin (one-shot)
print("\n=== Test 2: Admin creates user with role=client ===")
u2 = User.objects.create_user(
    email='t2_client@test.com', full_name='T2 Client', password='p',
    role='client', phone='+250780000002'
)
d2 = Driver.objects.filter(user=u2).count()
c2 = Customer.objects.filter(user=u2).count()
print(f"  Drivers: {d2} (expect 0) | Customers: {c2} (expect 1)")
results.append(d2 == 0 and c2 == 1)

# TEST 3: Driver form flow — driver saved first, then user created
print("\n=== Test 3: Driver view flow (driver first, then user) ===")
d3 = Driver.objects.create(
    name='T3 View Driver', email='t3_viewdriver@test.com', phone='+250780000003',
    license_number='DRV-T3-001', license_expiry='2027-01-01', status='AVAILABLE'
)
# View creates user — signal should find the unlinked driver by email and link it
u3 = User.objects.create_user(
    email='t3_viewdriver@test.com', full_name='T3 View Driver', password='p',
    role='driver', phone='+250780000003'
)
# View then links (should be same record the signal already linked)
d3.refresh_from_db()
d3_drivers = Driver.objects.filter(user=u3).count()
d3_total = Driver.objects.filter(email='t3_viewdriver@test.com').count()
c3 = Customer.objects.filter(user=u3).count()
print(f"  Drivers with user: {d3_drivers} (expect 1) | Total by email: {d3_total} (expect 1) | Customers: {c3} (expect 0)")
results.append(d3_drivers == 1 and d3_total == 1 and c3 == 0)

# TEST 4: Customer form flow — customer saved first, then user
print("\n=== Test 4: Customer view flow (customer first, then user) ===")
c4_obj = Customer.objects.create(
    company_name='T4 Corp', contact_person='T4 Contact', email='t4_cust@test.com',
    phone='+250780000004', status='ACTIVE'
)
u4 = User.objects.create_user(
    email='t4_cust@test.com', full_name='T4 Contact', password='p',
    role='client', phone='+250780000004'
)
c4_obj.refresh_from_db()
c4_custs = Customer.objects.filter(user=u4).count()
c4_total = Customer.objects.filter(email='t4_cust@test.com').count()
d4 = Driver.objects.filter(user=u4).count()
print(f"  Customers with user: {c4_custs} (expect 1) | Total by email: {c4_total} (expect 1) | Drivers: {d4} (expect 0)")
results.append(c4_custs == 1 and c4_total == 1 and d4 == 0)

# Summary
print(f"\n=== Results: {sum(results)}/{len(results)} passed ===")
for i, r in enumerate(results, 1):
    print(f"  Test {i}: {'PASS' if r else 'FAIL'}")

# Cleanup
for u in [u1, u2, u3, u4]:
    u.delete()
Driver.objects.filter(email__endswith='@test.com').delete()
Customer.objects.filter(email__endswith='@test.com').delete()
print("\nCleanup done")
