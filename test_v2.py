"""Engineering verification of fuzzy policy, evidence joins and Agent/UI wiring.

Synthetic cases test arithmetic and failure boundaries, never Malaysian market
accuracy or independently assessed recommendation relevance.
"""
import json
import unittest
from copy import deepcopy
from datetime import date
from pathlib import Path
from pydantic import ValidationError
from fuzzy_lifestyle import memberships, infer_lifestyle
from vehicle_evidence import load_catalogue, evidence_for_vehicle, _review_reference, ReviewEvidence, Source, source_date, EvidenceCatalogue
from lifestyle_v2 import rank_vehicles_v2
from test_scoring import vehicle, profile
from matching import filter_vehicles
from form_inputs import prepare_form
from agent_grounding import apply_patch
from agent_state import SessionState, SlotUpdate
from agent_tools import ToolRuntime, verify_observation
from agent_controller import AgentController
from test_agent import ScriptedBackend, sensed, planned, update
from test_streamlit_ui import session
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent
AS_OF = date(2026, 10, 15)


def exact(model='Myvi', year=2022, variant='1.5 AV', transmission='Automatic'):
    return dict(brand='Perodua', model=model, year=year, variant=variant, transmission=transmission)


class FuzzyTests(unittest.TestCase):
    def test_memberships_cover_domain_and_endpoints(self):
        for i in range(101):
            self.assertAlmostEqual(sum(memberships(i/100).values()), 1)
        self.assertEqual(memberships(0), {'low': 1, 'medium': 0, 'high': 0})
        self.assertEqual(memberships(.5)['medium'], 1)
        self.assertEqual(memberships(1)['high'], 1)

    def test_reject_nonfinite_and_boolean(self):
        for value in (True, float('nan'), float('inf'), '0.5'):
            with self.assertRaises(ValueError):
                memberships(value)
        with self.assertRaises(ValueError):
            infer_lifestyle(fuel=.5, fuel_weight=-1)

    def test_nine_rules_and_hand_calculated_balance(self):
        trace = infer_lifestyle(fuel=1, luggage=0, fuel_weight=4, luggage_weight=3)
        self.assertEqual(len(trace['rules']), 9)
        self.assertAlmostEqual(trace['denominator'], 1)
        self.assertAlmostEqual(trace['normalized_value'], .8*4/7)
        self.assertAlmostEqual(sum(r['contribution'] for r in trace['rules']), trace['numerator'])

    def test_single_input_and_missing_are_different_from_zero(self):
        self.assertEqual(infer_lifestyle(fuel=0, fuel_weight=1)['normalized_value'], 0)
        self.assertEqual(len(infer_lifestyle(fuel=.25, fuel_weight=1)['rules']), 3)
        self.assertIsNone(infer_lifestyle(fuel=1, fuel_weight=1, luggage_weight=1)['normalized_value'])
        self.assertIsNone(infer_lifestyle()['normalized_value'])

    def test_monotone_and_symmetric_policy(self):
        for boot in (0, .25, .5, .75, 1):
            scores = [infer_lifestyle(fuel=i/20, luggage=boot, fuel_weight=2, luggage_weight=2)['normalized_value'] for i in range(21)]
            self.assertEqual(scores, sorted(scores))
        a = infer_lifestyle(fuel=.3, luggage=.7, fuel_weight=2, luggage_weight=3)['normalized_value']
        b = infer_lifestyle(fuel=.7, luggage=.3, fuel_weight=3, luggage_weight=2)['normalized_value']
        self.assertAlmostEqual(a, b)


class EvidenceTests(unittest.TestCase):
    def test_catalogue_scope_and_unknown_reliability(self):
        self.assertEqual(len(load_catalogue().profiles), 7)
        for identity in (exact('Alza', 2020, '1.5 SE'), exact(year=2021), exact(variant='1.3 G'), exact(transmission='Manual')):
            e = evidence_for_vehicle(identity, as_of=AS_OF)
            self.assertIsNone(e['profile_id'])
            self.assertIsNone(e['safety']['normalized_value'])
        self.assertIsNone(evidence_for_vehicle(exact(), as_of=AS_OF)['reliability']['normalized_value'])

    def test_safety_partial_is_not_absent_and_stars_not_inherited(self):
        e = evidence_for_vehicle(exact(), as_of=AS_OF)['safety']
        self.assertAlmostEqual(e['normalized_value'], 2/3)
        self.assertAlmostEqual(e['data_coverage'], 2/3)
        self.assertAlmostEqual(e['upper_bound'], 1)
        self.assertIsNone(e['features']['curtain_airbags'])
        self.assertIsNone(e['report']['stars'])

    def test_same_year_persona_research_is_not_automatic_match(self):
        p = next(p for p in load_catalogue().profiles if p.model == 'Persona')
        v = dict(brand=p.brand, model=p.model, year=2021, variant=p.variants[0], transmission=p.transmissions[0])
        self.assertIsNone(evidence_for_vehicle(v, as_of=AS_OF)['profile_id'])
        research = evidence_for_vehicle(v, as_of=AS_OF, research_profile_id=p.profile_id)
        self.assertEqual(len(research['reviews']), 1)
        self.assertIn('Pre-MC2', research['scope']['generation'])

    def test_older_asof_and_month_precision(self):
        s = Source(source_id='x', family='x', author='x', url='https://example.org', locator='test', published_month='2021-11')
        self.assertEqual(source_date(s), date(2021, 11, 30))
        e = evidence_for_vehicle(exact(), as_of=date(2021, 11, 1))
        self.assertIsNone(e['safety']['normalized_value'])
        self.assertIsNone(e['comfort']['normalized_value'])

    def test_two_sources_and_hand_comfort_score(self):
        comfort = evidence_for_vehicle(exact(), as_of=AS_OF)['comfort']
        self.assertEqual(len(comfort['independent_source_families']), 2)
        # Seat 0; ride 0; noise mean(.5,0)=.25; rear 1 => 1.25/4.
        self.assertAlmostEqual(comfort['normalized_value'], .3125)
        self.assertEqual(comfort['data_coverage'], 1)
        alza = evidence_for_vehicle(exact('Alza', 2022, '1.5 AV'), as_of=AS_OF)
        self.assertIsNone(alza['comfort']['normalized_value'])

    def test_syndication_cannot_become_independent_and_conflict_visible(self):
        reviews = load_catalogue().profiles[1].reviews
        copy = reviews[0].model_copy(deep=True)
        copy.source.source_id = 'companion_video'
        self.assertIsNone(_review_reference([reviews[0], copy], 'comfort')['normalized_value'])
        contrary = reviews[1].model_copy(deep=True)
        contrary.seat_support = 'positive'
        self.assertIn('seat_support', _review_reference([reviews[0], contrary], 'comfort')['disagreements'])

    def test_missing_aspects_do_not_gain_weight(self):
        reviews = [r.model_copy(deep=True) for r in load_catalogue().profiles[1].reviews]
        for r in reviews:
            r.ride_comfort = r.highway_noise = 'unknown'
        result = _review_reference(reviews, 'comfort')
        self.assertAlmostEqual(result['data_coverage'], .5)
        self.assertAlmostEqual(result['normalized_value'], .25)
        self.assertAlmostEqual(result['upper_bound'], .75)

    def test_short_drive_cannot_claim_reliability_and_sources_are_safe(self):
        review = load_catalogue().profiles[1].reviews[0].model_dump(mode='json')
        review['reliability'] = 'positive'
        with self.assertRaises(ValidationError):
            ReviewEvidence.model_validate_json(json.dumps(review))
        review['source']['url'] = 'javascript:alert(1)'
        with self.assertRaises(ValidationError):
            ReviewEvidence.model_validate_json(json.dumps(review))

    def test_duplicate_profile_rejected(self):
        catalogue = load_catalogue().model_dump(mode='json')
        catalogue['profiles'].append(deepcopy(catalogue['profiles'][0]))
        with self.assertRaises(ValidationError):
            EvidenceCatalogue.model_validate_json(json.dumps(catalogue))

    def test_brochure_cannot_become_crash_rating(self):
        from vehicle_evidence import SafetyEvidence
        data = load_catalogue().profiles[1].safety.model_dump(mode='json')
        data['stars'] = 5
        with self.assertRaises(ValidationError):
            SafetyEvidence.model_validate_json(json.dumps(data))

    def test_two_owner_opinions_are_not_failure_probability(self):
        # Synthetic coding records exercise the engine, not real owner claims.
        records = [r.model_copy(deep=True) for r in load_catalogue().profiles[1].reviews]
        for r, code in zip(records, ('positive', 'negative')):
            r.context, r.ownership_months, r.reliability = 'owner_report', 24, code
        result = _review_reference(records, 'reliability')
        self.assertAlmostEqual(result['normalized_value'], .5)
        self.assertIn('reliability', result['disagreements'])
        self.assertIn('not a failure rate', result['policy'])


class V2IntegrationTests(unittest.TestCase):
    def test_fuzzy_replaces_old_components_and_preserves_filter(self):
        p = profile(fuel_priority='high', space_priority='high', excluded_brands=['Excluded'])
        cars = [vehicle('ok', 30000, 22, boot_litres=400, boot_configuration='all_seats_up', specs_source_reference='Fixture'), vehicle('over', 60000, 25), vehicle('excluded', 10000, 25, brand='Excluded')]
        filtered = filter_vehicles(p, cars)
        before = deepcopy(filtered)
        result = rank_vehicles_v2(p, filtered)
        self.assertEqual(filtered, before)
        self.assertEqual(result['top_vehicle_ids'], ['ok'])
        self.assertNotIn('fuel', result['scoring_weights'])
        self.assertNotIn('luggage', result['scoring_weights'])
        self.assertEqual(len(result['matches'][0]['fuzzy_trace']['rules']), 9)

    def test_unknown_fuzzy_no_imputation_or_renormalization(self):
        p = profile(fuel_priority='high', space_priority='high')
        result = rank_vehicles_v2(p, filter_vehicles(p, [vehicle('missing', 30000, 22)]))
        row = result['matches'][0]
        self.assertIsNone(row['score_breakdown']['fuzzy_lifestyle']['normalized_value'])
        self.assertGreater(row['score_upper_bound'], row['score'])
        self.assertLess(row['weighted_data_coverage_percent'], 100)

    def test_mixed_cycles_disable_fuel_globally(self):
        p = profile(fuel_priority='high')
        r = rank_vehicles_v2(p, filter_vehicles(p, [vehicle('a', 30000, 20), vehicle('b', 30000, 20, fuel_basis='MDC_claim')]))
        self.assertNotIn('fuzzy_lifestyle', r['scoring_weights'])
        self.assertTrue(any('incompatible' in n for n in r['scoring_notes']))

    def test_new_priorities_survive_form_and_verified_controller(self):
        ui = session('inspect_requirements', 'rank_vehicles', 'check_result', 'finish')
        text, patch = prepare_form('buy', {'buyer.budget_myr': '60000', 'buyer.required_seats': '5', 'buyer.usage': 'City commuting', 'buyer.safety_priority': 'high', 'buyer.comfort_priority': 'medium', 'buyer.reliability_priority': 'high'})
        ui.submit(text, goal='buy', form_patch=patch)
        self.assertEqual(ui.last_response['status'], 'complete')
        self.assertEqual(ui.controller.state.buyer.safety_priority, 'high')
        self.assertIn('reliability', ui.last_response['result']['scoring_weights'])
        self.assertTrue(all(c['passed'] for c in ui.last_response['checks']))

    def test_unrelated_and_inverted_priority_are_rejected(self):
        from agent_grounding import grounded_value
        for evidence, value in [('Fuel priority is high.', 'high'), ('Safety priority is low.', 'high'), ('Safety priority is not high.', 'high')]:
            with self.assertRaises(ValueError):
                grounded_value(SlotUpdate(slot='buyer.safety_priority', value=value, evidence=evidence), evidence, SessionState(goal='buy'))

    def test_checker_rejects_tampered_sources_trace_and_bounds(self):
        state = SessionState(goal='buy', buyer=profile(fuel_priority='high', safety_priority='high'))
        cars = [vehicle('a', 30000, 20)]
        runtime = ToolRuntime(state, cars, AS_OF)
        runtime.call('inspect_requirements', {})
        result = runtime.call('rank_vehicles', {})
        self.assertTrue(all(c['passed'] for c in verify_observation('rank_vehicles', result, state, cars, AS_OF)))
        for field, value in [('score_upper_bound', 0), ('fuzzy_trace', {}), ('vehicle_evidence', {})]:
            forged = deepcopy(result)
            forged['matches'][0][field] = value
            self.assertTrue(any(not c['passed'] for c in verify_observation('rank_vehicles', forged, state, cars, AS_OF)))

    def test_english_chat_pref_changes_use_actual_tools(self):
        message = 'I want to buy a car. Safety is important. Comfort priority is medium.'
        backend = ScriptedBackend(sensed('buy', 'buy a car', [update('buyer.safety_priority', 'high', 'Safety is important'), update('buyer.comfort_priority', 'medium', 'Comfort priority is medium')]), planned('inspect_requirements', 'rank_vehicles', 'check_result', 'finish'))
        agent = AgentController(backend=backend, state=SessionState(goal='buy', buyer=profile()), as_of=AS_OF)
        result = agent.handle(message)
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(agent.state.buyer.comfort_priority, 'medium')

    def test_explicit_usage_recovers_actual_model_omission(self):
        message = 'I want to buy a car. Budget RM60000. I need 5 seats for city commuting.'
        backend = ScriptedBackend(sensed('buy', 'buy a car', [update('buyer.budget_myr', 60000, 'Budget RM60000'), update('buyer.required_seats', 5, 'I need 5 seats')]), planned('inspect_requirements', 'rank_vehicles', 'check_result', 'finish'))
        agent = AgentController(backend=backend, as_of=AS_OF)
        result = agent.handle(message)
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(agent.state.buyer.usage, ['city_commute'])
        self.assertTrue(any(e.get('rule_id') == 'BUY_USAGE_SOURCE' for e in result['trace']))

    def test_negated_or_unstated_usage_never_recovered(self):
        from input_grounding import explicit_buyer_usages
        for text in ('No city commuting.', 'Do not use it for family travel.', 'Remove long-distance driving.', 'Fuel priority is high.'):
            self.assertEqual(explicit_buyer_usages(text), [])

    def test_research_browser_is_readonly_and_actual_buy_result_renders(self):
        ui = session('inspect_requirements', 'rank_vehicles', 'check_result', 'finish')
        app = AppTest.from_file(str(ROOT/'streamlit_app.py'), default_timeout=30)
        app.session_state['ui_session'] = ui
        app.run()
        app.button(key='nav_research').click().run()
        app.selectbox(key='research_profile').set_value('MYVI_FACELIFT_2022_AV').run()
        self.assertFalse(app.exception)
        self.assertEqual(ui.controller.backend.requests, [])
        text, patch = prepare_form('buy', {'buyer.budget_myr': '60000', 'buyer.required_seats': '5', 'buyer.usage': 'City commuting', 'buyer.safety_priority': 'high'})
        ui.submit(text, goal='buy', form_patch=patch)
        app.button(key='nav_results').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any('sugeno-lifestyle-v2.0' in c.value for c in app.caption))


if __name__ == '__main__':
    unittest.main()
