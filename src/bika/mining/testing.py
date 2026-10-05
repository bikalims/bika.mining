# -*- coding: utf-8 -*-
from senaite.core.tests.layers import BASE_LAYER_FIXTURE
from plone.app.robotframework.testing import REMOTE_LIBRARY_BUNDLE_FIXTURE
from plone.app.testing import (
    applyProfile,
    FunctionalTesting,
    IntegrationTesting,
    PloneSandboxLayer,
)
from plone.testing import z2

import bika.mining


class BikaMiningLayer(PloneSandboxLayer):

    defaultBases = (BASE_LAYER_FIXTURE,)

    def setUpZope(self, app, configurationContext):
        # Load any other ZCML that is required for your tests.
        # The z3c.autoinclude feature is disabled in the Plone fixture base
        # layer.
        import plone.restapi
        self.loadZCML(package=plone.restapi)
        self.loadZCML(package=bika.mining)

    def setUpPloneSite(self, portal):
        applyProfile(portal, 'bika.mining:default')


BIKA_MINING_FIXTURE = BikaMiningLayer()


BIKA_MINING_INTEGRATION_TESTING = IntegrationTesting(
    bases=(BIKA_MINING_FIXTURE,),
    name='BikaMiningLayer:IntegrationTesting',
)


BIKA_MINING_FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(BIKA_MINING_FIXTURE,),
    name='BikaMiningLayer:FunctionalTesting',
)


BIKA_MINING_ACCEPTANCE_TESTING = FunctionalTesting(
    bases=(
        BIKA_MINING_FIXTURE,
        REMOTE_LIBRARY_BUNDLE_FIXTURE,
        z2.ZSERVER_FIXTURE,
    ),
    name='BikaMiningLayer:AcceptanceTesting',
)
