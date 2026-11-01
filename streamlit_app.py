r"""English browser UI over the existing local consultation Agent Controller.

Run: .\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
Only explicit submit events run a turn. Browsing/rendering never calls a model.
"""
from uuid import uuid4
import streamlit as st
from form_inputs import GOALS, USAGES, fields_for, current_value, prepare_form
from ui_session import UISession, display_money, source_url, verified_result
from vehicle_evidence import load_catalogue, evidence_for_vehicle
from vehicle_presentation import vehicle_information_lines, mileage_text, fuel_reference_text
from question_examples import form_guidance, catalogue_notice


# Store explicit submissions for one run, rather than run on every widget edit.
def queue_turn(text, goal, patch=None):
    if st.session_state.get('busy') or st.session_state.get('pending_turn') or st.session_state.get('blocked_turn'):
        return
    st.session_state.pending_turn = {'text': text, 'goal': goal, 'patch': patch, 'request_id': uuid4().hex}
    st.session_state.busy = True
    st.session_state.active_view = 'consultation'
    st.rerun()


def open_view(view):
    # Navigation reads saved results; it never submits another consultation.
    st.session_state.active_view = view


def request_cancellation():
    ui = st.session_state.ui_session
    if ui.active_turn is not None:
        ui.active_turn.cancel()
    elif st.session_state.get('pending_turn'):
        st.session_state.pop('pending_turn')
        st.session_state.busy = False
        ui.submit('/stop', goal=ui.controller.state.goal or 'buy')


def collect_finished_turn(ui):
    if ui.active_turn is not None and ui.active_turn.done.is_set():
        ui.finish_background()
        st.session_state.busy = False
        if ui.controller.state.goal:
            st.session_state.next_area = ui.controller.state.goal
        return True
    return False


@st.fragment(run_every=.2)
def watch_calculation():
    """Refresh status while the worker runs, leaving the Stop button responsive."""
    ui = st.session_state.ui_session
    if collect_finished_turn(ui):
        st.rerun()
    if ui.active_turn is not None:
        if ui.active_turn.cancellation.is_set():
            st.info('Stopping the current calculation…')
        else:
            st.info('Working on your request… Select Stop at the upper right to cancel.')


def render_confirmed_details(state):
    """Show remembered customer inputs as readable labels, without changing them."""
    active_goal = state.goal
    if active_goal not in GOALS:
        st.info('No confirmed details yet. Send a message to start your consultation.')
        return
    st.caption('Consultation: ' + GOALS[active_goal])
    rows = []
    for field in fields_for(active_goal):
        value = current_value(state, field.path)
        if value is None or value == [] or value == '':
            continue
        if field.kind == 'money':
            shown = display_money(value)
        elif field.kind == 'boolean':
            shown = 'Yes' if value else 'No'
        elif field.kind == 'usage':
            shown = ', '.join(label for label, key in USAGES.items() if key in value)
        elif isinstance(value, list):
            shown = ', '.join(value)
        elif field.kind == 'distance':
            shown = f'{value:g} km'
        else:
            shown = str(value).replace('_', ' ')
        label = field.label if field.group == 'Details' else field.group + ' · ' + field.label
        rows.append({'Detail': label, 'Confirmed value': shown})
    if rows:
        st.table(rows)
    else:
        st.info('Your confirmed details will appear here after you send a message.')
    pending_usage = state.provenance.get('buyer.usage_pending') if active_goal == 'buy' else None
    if pending_usage:
        st.caption('Use described: ' + pending_usage['evidence'] + ' (category awaiting clarification).')
    for question in dict.fromkeys(state.issues.values()):
        st.warning(question)


# Source links show saved evidence; they do not fetch or refresh advertisements.
def render_source(label, url):
    safe = source_url(url)
    if safe:
        st.link_button(label, safe)


def render_vehicle_evidence(evidence):
    # Keep report context and attributed opinions beside, not hidden behind, scores.
    st.caption('Evidence reviewed: ' + evidence['evidence_reviewed_on'] + ' · saved research, not live verification')
    st.json({'applicability': evidence['scope'], 'limits': evidence['limits']}, expanded=False)
    for name in ('safety', 'comfort', 'reliability'):
        item = evidence[name]
        value = item['normalized_value']
        st.markdown('**' + name.title() + '**: ' + ('Unknown' if value is None else f"{100*value:.1f}/100 supported points; {100*item['data_coverage']:.1f}% evidence coverage"))
        st.caption(item['label'])
        if item.get('unknown_reason'):
            st.caption(item['unknown_reason'])
        st.caption(item['policy'])
        if name == 'safety':
            st.write(item['features'])
            report = item['report']
            if report:
                st.caption(f"Protocol: {report['protocol']} · tested/reference variant: {report['tested_variant']} · stars: {report['stars'] if report['stars'] is not None else 'Not assigned'}")
                render_source('Safety source', report['source']['url'])
                for limitation in report['limits']:
                    st.caption(limitation)
        elif item['disagreements']:
            st.caption('Opposing review opinions: ' + ', '.join(item['disagreements']))
    for review in evidence['reviews']:
        st.markdown('**' + review['source']['author'] + ' · ' + (review['source']['published_on'] or review['source']['published_month'] or 'Date unknown') + '**')
        st.write(review['summary'])
        st.caption('Context: ' + review['context'] + ' · source family: ' + review['source']['family'])
        for limitation in review['limits']:
            st.caption(limitation)
        render_source('Read attributed review', review['source']['url'])


def render_research_catalogue():
    # Research browsing never adds stock, selects a vehicle or calls a model.
    catalogue = load_catalogue()
    st.subheader('Vehicle research catalogue')
    st.info('Research profiles are not available stock or purchase recommendations. Prices, fees and availability are unknown here. Use the consultation to match saved advertisements against your budget.')
    st.caption(catalogue.notice)
    profiles = {p.profile_id: p for p in catalogue.profiles}
    chosen = st.selectbox('Research profile', list(profiles), format_func=lambda key: f"{profiles[key].brand} {profiles[key].model} · {profiles[key].years} · {', '.join(profiles[key].variants)}", key='research_profile')
    p = profiles[chosen]
    identity = dict(brand=p.brand, model=p.model, year=p.years[0], variant=p.variants[0], transmission=p.transmissions[0])
    st.caption('Price: Unknown · Fees: Unknown · Availability: Unknown · Evidence check date: ' + catalogue.reviewed_on.isoformat())
    if not p.automatic_matching:
        st.warning('Research context only: the saved year does not resolve all model changes. Automatic advertisement matching is disabled for this profile.')
    render_vehicle_evidence(evidence_for_vehicle(identity, as_of=catalogue.reviewed_on, catalogue=catalogue, research_profile_id=p.profile_id))


# Keep table rows simple and preserve unknowns explicitly instead of NaN/zero guesses.
def render_buy(result):
    st.subheader('Compare eligible vehicles')
    if not result['matches']:
        st.info('No saved listing matches your current requirements. You can change your budget, minimum seats or excluded brands in chat or the details form. Your requirements stay in effect until you change them.')
    else:
        preferred = result['buyer_reasoning']['extracted_profile']['preferred_brands']
        eligible_brands = {row['vehicle']['brand'].casefold() for row in result['matches']}
        unavailable = [brand for brand in preferred if brand.casefold().strip() not in eligible_brands]
        if unavailable:
            st.info('No eligible saved listing was found for your preferred brand(s): ' + ', '.join(unavailable) + '. Other eligible brands are shown below; your preference is still recorded.')
        rows = result['matches'][:3]
        columns = st.columns(len(rows))
        for column, row in zip(columns, rows):
            car = row['vehicle']
            with column, st.container(border=True):
                st.caption(f"RANK {row['rank']}")
                st.markdown(f"**{car['year']} {car['brand']} {car['model']}**")
                st.text(car.get('variant') or 'Variant unknown')
                # Normal text wraps on narrow windows; oversized metric text
                # would truncate the amount and hide important price digits.
                st.caption('Reference price')
                st.markdown('**' + display_money(car['price_myr']) + '**')
                for line in vehicle_information_lines(car)[1:]:
                    st.write(line)
        comparison = []
        for row in rows:
            v = row['vehicle']
            comparison.append({'Rank': row['rank'], 'Vehicle': f"{v['year']} {v['brand']} {v['model']} {v.get('variant') or ''}",
                               'Reference price': display_money(v['price_myr']), 'Seats': v['seats'],
                               'Transmission': v.get('transmission') or 'Unknown',
                               'Mileage': mileage_text(v) or 'Unknown', 'Fuel reference': fuel_reference_text(v) or 'Unknown',
                               'Boot (L)': v.get('boot_litres'), 'Length (mm)': v.get('length_mm')})
        st.dataframe(comparison, hide_index=True, width='stretch')
        with st.expander('Vehicle details and sources'):
            for row in rows:
                car = row['vehicle']
                st.markdown(f"**Rank {row['rank']} · {car['brand']} {car['model']}**")
                st.caption('Record ID: ' + car['vehicle_id'])
                st.caption('Source observation date: ' + (car.get('observed_on') or 'Unknown'))
                render_source('Source reference', car['source_reference'])
                if car.get('specs_source_reference'):
                    render_source('Specification reference', car['specs_source_reference'])
        with st.expander('Score calculation, weights and missing features'):
            st.json({'weights': result['scoring_weights'], 'formulas': result['scoring_anchors']})
            for row in rows:
                st.markdown('**' + row['vehicle']['vehicle_id'] + '**')
                st.dataframe([{'Feature': name, **component} for name, component in row['score_breakdown'].items()], hide_index=True, width='stretch')
                st.caption('Unknown: ' + (', '.join(row['missing_scoring_features']) or 'None'))
                st.caption(row['ranking_explanation'])
            for note in result.get('scoring_notes', []):
                st.caption(note)
        if result.get('ranking_policy'):
            with st.expander('Fuzzy rules, safety and attributed review evidence'):
                st.caption('Ranking policy: ' + result['ranking_policy'] + ' · evidence as-of: ' + result['evidence_as_of'])
                for row in rows:
                    st.markdown('**' + row['vehicle']['vehicle_id'] + '**')
                    st.json(row['fuzzy_trace'], expanded=False)
                    render_vehicle_evidence(row['vehicle_evidence'])
    with st.expander('Hard constraints and rejected records'):
        st.json({'constraints': result['constraints'], 'rejected': result['rejected']})


# The UI never fabricates an adjustment table when default valuation is unadjusted.
def render_historical_reference(model):
    """Keep the learned historical prediction visibly distinct from real quotes."""
    st.markdown('**Historical regression reference**')
    st.metric('Estimated historical asking price', display_money(model['estimated_asking_price_myr']))
    st.caption('Historical ads + simulation data. Not current market value, a dealer offer or guaranteed sale proceeds.')
    score = model['evaluation']
    st.write('Development average absolute error: ' + display_money(score['mae_myr']) +
             f" across {score['group_count']} held-out source groups.")
    low, high = model['illustrative_error_band_myr']
    st.caption('Illustrative error guide: ' + display_money(low) + ' – ' + display_money(high) +
               '. Prediction ± average development error; not a confidence interval or guaranteed range.')
    with st.expander('Historical model scope, inputs and sources'):
        st.json(model)


def render_value(result):
    st.subheader('Asking-price reference')
    reference = result.get('reference')
    if result.get('status') == 'historical_reference':
        render_historical_reference(result['historical_regression'])
    elif not reference:
        st.info(result.get('message', 'No numeric reference is available for this outcome.'))
    else:
        left, right = st.columns(2)
        left.caption('Median asking price')
        left.markdown('**' + display_money(reference['median_asking_price_myr']) + '**')
        low, high = reference['observed_asking_range_myr']
        right.caption('Observed asking range')
        right.markdown('**' + display_money(low) + ' – ' + display_money(high) + '**')
        st.caption(f"{reference['comparable_count']} eligible comparable snapshots; not verified transaction prices.")
        st.info('No mileage/condition adjustment applied. Market-calibrated condition/damage penalties are outside the agreed v2 scope.')
        st.dataframe([{'Step': 'Comparable asking median', 'Amount / treatment': display_money(reference['median_asking_price_myr'])},
                      {'Step': 'Mileage adjustment', 'Amount / treatment': 'Not applied; not market-calibrated'},
                      {'Step': 'Condition adjustment', 'Amount / treatment': 'Not applied; not market-calibrated'}], hide_index=True, width='stretch')
    if result.get('comparables'):
        st.dataframe(result['comparables'], hide_index=True, width='stretch')
        for row in result['comparables']:
            render_source('Comparable ' + row['vehicle_id'], row['source_reference'])
    with st.expander('Comparable selection, policy and exclusions'):
        st.json({key: result.get(key) for key in ('as_of', 'policy', 'excluded_records', 'fired_rules')})
    for limitation in result.get('limitations', []):
        st.caption(limitation)


# Show reference provenance separately from the user's current quote/bid.
def render_asking_context(evidence):
    reference = (evidence or {}).get('reference')
    if (evidence or {}).get('historical_regression'):
        render_historical_reference(evidence['historical_regression'])
    elif reference:
        st.markdown('**Linked website asking-price context**')
        st.write('Median: ' + display_money(reference['median_asking_price_myr']))
        st.caption('Saved asking prices are context, not a dealer cash offer or guaranteed sale proceeds.')
        for row in evidence.get('sources', []):
            render_source(row['vehicle_id'], row['source_reference'])
    else:
        st.caption('No usable linked website asking-price reference. No market price is invented.')


# Negotiation displays the tree's bounded action and reconciled total/net figures.
def render_negotiation(result):
    st.subheader('Negotiation advice')
    if result.get('action'):
        st.write('Suggested action: **' + result['action'].replace('_', ' ') + '**')
    if result.get('suggested_counter_price_myr') is not None:
        st.metric('Suggested bare vehicle-price counter', display_money(result['suggested_counter_price_myr']))
    st.json(result.get('calculations', {}))
    render_asking_context(result.get('valuation_evidence'))
    for limitation in result.get('limitations', []):
        st.caption(limitation)


# Preserve signed totals and four distinct quote roles in a side-by-side table.
def render_trade(result):
    st.subheader('Trade-in vs private sale')
    st.caption('Financial amounts are user-provided quotes, not authenticated dealer documents. Time and effort are user estimates.')
    paths = result.get('paths', {})
    fields = [('Replacement price', 'replacement_price_myr'), ('Replacement fees', 'replacement_fees_myr'),
              ('Gross disposal offer', 'gross_offer_myr'), ('Disposal fees', 'disposal_fees_myr'),
              ('Old-loan settlement', 'loan_settlement_myr'), ('Net disposal proceeds', 'net_proceeds_myr'),
              ('Signed cash difference', 'cash_difference_myr'), ('Additional cash required', 'cash_required_myr'),
              ('Cash surplus', 'cash_surplus_myr')]
    if paths:
        st.dataframe([{'Calculation': title, **{name.replace('_', ' ').title(): display_money(row.get(key)) for name, row in paths.items()}}
                      for title, key in fields], hide_index=True, width='stretch')
        st.caption('Positive cash difference needs additional cash; negative means a surplus. The old loan is settled once per alternative.')
        st.dataframe([{'Path': name.replace('_', ' '), 'Within stated cash limit': row.get('within_available_cash'),
                       'Estimated days': row.get('estimated_completion_days'), 'Estimated effort hours': row.get('estimated_effort_hours')}
                      for name, row in paths.items()], hide_index=True, width='stretch')
    if result.get('suggested_path'):
        st.success('Conditional path for your stated priority: ' + result['suggested_path'].replace('_', ' '))
    if result.get('message'):
        st.info(result['message'])
    render_asking_context(result.get('asking_price_context'))
    with st.expander('Cash formulas, comparison and limits'):
        st.json({key: result.get(key) for key in ('policy', 'comparison', 'limitations')})


# Every widget starts blank: old quotes cannot be accidentally reconfirmed by a
# form whose only intended change was the vehicle identity.
def render_form(ui, goal, busy):
    with st.expander('Add or update details with a form', expanded=False):
        st.caption('Blank = keep confirmed facts. Enter Unknown to clear a value. Enter 0 only for a confirmed zero; prices must be positive.')
        st.caption('Driving use: selected uses replace confirmed uses. Empty keeps them; Unknown alone clears them. Brand lists replace the previous list.')
        notice = catalogue_notice(ui.controller.state, ui.controller.cars, goal=goal)
        if notice:
            st.info(notice)
        with st.form(f'details_{goal}_{ui.generation}'):
            entries, previous_group = {}, None
            columns = None
            index = 0
            for field in fields_for(goal):
                if field.group != previous_group:
                    st.markdown('**' + field.group + '**')
                    previous_group, index = field.group, 0
                    columns = st.columns(2)
                current = current_value(ui.controller.state, field.path)
                help_text = 'Confirmed: ' + str(current if current is not None else 'Unknown') + '. Blank keeps this fact.'
                example, placeholder = form_guidance(field, ui.controller.state, ui.controller.cars, goal=goal)
                if example:
                    help_text += ' Example guidance: ' + example
                key = f'field_{goal}_{ui.generation}_{field.path}'
                with columns[index % 2]:
                    if field.kind == 'usage':
                        selected = st.multiselect(field.label, [*USAGES, 'Unknown'], key=key, help=help_text, disabled=busy)
                        entries[field.path] = ', '.join(selected)
                    elif field.kind in ('choice', 'boolean'):
                        options = ['', 'Yes', 'No', 'Unknown'] if field.kind == 'boolean' else ['', *field.choices, 'Unknown']
                        entries[field.path] = st.selectbox(field.label, options, key=key, help=help_text, disabled=busy,
                                                          format_func=lambda value: 'Keep / not provided' if value == '' else value)
                    else:
                        entries[field.path] = st.text_input(field.label, key=key, help=help_text, disabled=busy, max_chars=160,
                                                           placeholder=placeholder)
                    if example:
                        st.caption(example)
                index += 1
            unit = st.selectbox('Odometer unit', ['km', 'm', 'miles'], disabled=busy) if goal != 'buy' else 'km'
            submitted = st.form_submit_button('Submit details to Agent', type='primary', disabled=busy)
        if submitted:
            try:
                message, patch = prepare_form(goal, entries, ui.controller.state, mileage_unit=unit)
                queue_turn(message, goal, patch)
            except ValueError as error:
                st.error(str(error))


# A rerun with no queued submit only renders stored evidence; it makes no API call.
def main():
    st.set_page_config(page_title='Vehicle Consultation Agent', page_icon='🚗', layout='wide')
    # The requested four-color palette uses red for actions, brown for headings,
    # and neutral greys for surfaces. White keeps form fields easy to distinguish.
    st.markdown('''<style>
    /* The app Stop control owns cancellation; hide the framework's separate
       script-only running control to avoid two different Stop behaviours. */
    [data-testid="stStatusWidget"] {display: none;}
    [data-testid="stHeadingWithActionElements"] h1,
    [data-testid="stHeadingWithActionElements"] h2,
    [data-testid="stHeadingWithActionElements"] h3 {
        color: #6B2B06;
    }
    [data-testid="stCaptionContainer"] {color: #6B2B06;}
    .st-key-message_composer {
        background: #FFFFFF;
        border: 2px solid #B80C09;
        border-radius: 16px;
        padding: 1.1rem;
        margin-bottom: 0.8rem;
    }
    .st-key-message_composer strong {color: #6B2B06;}
    .st-key-message_composer textarea {font-size: 1.05rem;}
    .st-key-message_composer [data-testid="stChatInput"] {
        background: #E5E7E6;
        border: 1px solid #B7B5B3;
        border-radius: 12px;
    }
    .st-key-message_composer textarea::placeholder {color: #6B2B06; opacity: 1;}
    .st-key-message_composer [data-testid="stChatInput"]:focus-within {
        outline: 3px solid #B80C09;
        outline-offset: 2px;
    }
    </style>''', unsafe_allow_html=True)
    if 'ui_session' not in st.session_state:
        st.session_state.ui_session = UISession()
    ui = st.session_state.ui_session
    collect_finished_turn(ui)
    if 'next_area' in st.session_state:
        st.session_state.task_area = st.session_state.pop('next_area')
    executing = st.session_state.get('busy', False)
    # A blocked draft stays intact until Retry/Discard; it has not updated
    # facts. Disable new edits so retry cannot later overwrite newer facts.
    busy = executing or bool(st.session_state.get('blocked_turn'))
    with st.sidebar:
        st.title('Vehicle Agent')
        st.caption('Malaysia · Used vehicles · MYR')
        goal = st.selectbox('Consultation area', list(GOALS), format_func=GOALS.get, key='task_area', disabled=busy)
        st.caption('Browsing areas keeps facts unchanged. Submitting starts or switches the consultation.')
        st.divider()
        with st.popover('View confirmed details', icon=':material/fact_check:', width='stretch', disabled=executing):
            render_confirmed_details(ui.controller.state)
    st.title('Vehicle Sales & Purchase Consultation')
    st.write('Find suitable vehicles, review asking-price evidence and compare negotiation or trade-in choices.')
    if st.session_state.get('blocked_turn'):
        st.warning('The local model is serving another browser session. Your submission is kept in this tab and has not been applied. Retry when the model is free, or discard it. Existing results belong to the previous completed turn.')
        with st.expander('Saved submission awaiting Retry'):
            st.text(st.session_state.blocked_turn['text'])
        retry, discard = st.columns(2)
        if retry.button('Retry saved submission', key='retry_submission', disabled=executing):
            st.session_state.pending_turn = st.session_state.pop('blocked_turn')
            st.session_state.busy = True
            st.rerun()
        if discard.button('Discard saved submission', key='discard_submission', disabled=executing):
            st.session_state.pop('blocked_turn')
            ui.generation += 1  # Clear the discarded form's widget values too.
            st.rerun()
    view = st.session_state.get('active_view', 'consultation')
    navigation, stop_control, menu = st.columns([7, 1.5, 2], vertical_alignment='center')
    with navigation:
        if view != 'consultation':
            st.button('Back to consultation', icon=':material/chat:', key='nav_consultation',
                      on_click=open_view, args=('consultation',), disabled=executing)
    with stop_control:
        stopping = ui.active_turn is not None and ui.active_turn.cancellation.is_set()
        st.button('Stop', icon=':material/stop_circle:', key='cancel_calculation', width='stretch',
                  type='primary' if executing else 'secondary', disabled=not executing or stopping,
                  on_click=request_cancellation, help='Cancel the current calculation and keep previously confirmed details.')
    with menu:
        with st.popover('Menu', icon=':material/menu:', key='consultation_menu_' + view, width='stretch', disabled=executing):
            st.button('Results & comparison', key='nav_results', on_click=open_view, args=('results',), width='stretch')
            st.button('Evidence & checks', key='nav_evidence', on_click=open_view, args=('evidence',), width='stretch')
            st.button('Vehicle research', key='nav_research', on_click=open_view, args=('research',), width='stretch')
    if ui.active_turn is not None:
        watch_calculation()
    if view == 'research':
        render_research_catalogue()
    if view == 'consultation':
        st.subheader(GOALS[goal] + ' consultation')
        if not ui.history:
            st.caption('Start here. Tell us what you need, and the Agent will ask for any missing details.')
        for item in ui.history:
            with st.chat_message('user'):
                st.text(item['user'])
            with st.chat_message('assistant'):
                st.text(item['response']['message'])
                st.caption('Status: ' + item['response']['status'])
        budget_source = ui.controller.state.provenance.get('buyer.budget_myr', {})
        if ui.controller.state.goal == 'buy' and budget_source.get('turn') == ui.controller.state.turn:
            budget_issue = ui.controller.state.issues.get('buyer.budget_myr')
            if budget_issue:
                st.warning('Budget not accepted. ' + budget_issue)
            elif ui.controller.state.buyer.budget_myr is not None:
                st.caption('Budget recorded: ' + display_money(ui.controller.state.buyer.budget_myr) + ' maximum vehicle price.')
        with st.container(key='message_composer'):
            st.markdown('**Message the Agent**')
            if goal == 'buy':
                st.caption('Example: Budget RM60000, at least 5 seats, family travel, save fuel. You can also write RM1 million.')
            else:
                st.caption('Describe your vehicle and question in English. Include RM/MYR for money and km, m or miles for the odometer.')
            text = st.chat_input('Type your message here, then press Enter to send', key='chat_message', height=100,
                                 max_chars=6000, disabled=busy, submit_mode='disable')
        if text:
            queue_turn(text, goal)
        render_form(ui, goal, busy)
    if view == 'results':
        response = ui.last_response
        result = verified_result(response)
        if result is None:
            st.info('Results appear after the Agent executes the current task and passes its checks. Answer pending questions in the Consultation tab.')
        elif result['status'] == 'inspection_required':
            st.warning('Independent inspection required. No ordinary numeric valuation or deal recommendation is presented.')
        elif response['goal'] == 'buy':
            render_buy(result)
        elif response['goal'] == 'sell':
            render_value(result)
        elif response['goal'] == 'negotiate':
            render_negotiation(result)
        else:
            render_trade(result)
    if view == 'evidence':
        if ui.last_response:
            response = ui.last_response
            st.write('Consultation status: **' + response['status'] + '**')
            st.write('Executed tools: ' + (' → '.join(item['name'] for item in response['tools'] if item.get('executed')) or 'None'))
            for label, key in [('Facts', 'facts'), ('Rules', 'rules'), ('Tools and actual observations', 'tools'), ('Independent checks', 'checks')]:
                with st.expander(label):
                    st.json(response.get(key, {}))
            with st.expander('Complete current-turn trace and limits'):
                st.json({'trace': response['trace'], 'limits': response['limits']})
        else:
            st.info('The Agent records facts, rules, tool execution and checks after a submission.')
    if st.session_state.get('pending_turn'):
        # Pop before executing so any rerun cannot repeat this submitted request.
        pending = st.session_state.pop('pending_turn')
        if not ui.start_background(pending['text'], goal=pending['goal'], form_patch=pending['patch'], request_id=pending['request_id']):
            # Keep the original patch/ID; never automatically run a blocked draft.
            st.session_state.blocked_turn = pending
            st.session_state.busy = False
            st.rerun()
        else:
            if ui.active_turn is not None:
                # Fast local commands/tools need no separate waiting screen.
                ui.active_turn.done.wait(.03)
                collect_finished_turn(ui)
            else:
                st.session_state.busy = False
            st.rerun()


if __name__ == '__main__':
    main()
