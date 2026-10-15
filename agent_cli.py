"""Interactive English CLI for the local, tool-calling vehicle agent."""
import argparse
import json
from datetime import date
from pathlib import Path
from agent_controller import AgentController, OllamaBackend, load_session, save_session


def main():
    parser = argparse.ArgumentParser(description='Multi-turn local vehicle consultation Agent Loop')
    parser.add_argument('--model', default='qwen3:4b')
    parser.add_argument('--as-of', help='Reproduction date YYYY-MM-DD; otherwise today in Malaysia')
    parser.add_argument('--session', type=Path, help='Optional local JSON memory file; never treated as fresh tool observations')
    parser.add_argument('--message', help='One turn, optionally continuing a saved session')
    parser.add_argument('--script', type=Path, help='JSON list of English user messages to replay in one session')
    parser.add_argument('--json', action='store_true', help='Print structured facts, rules, tools, checks and results')
    args = parser.parse_args()
    if args.message and args.script:
        parser.error('Choose either --message or --script')
    try:
        agent = AgentController(state=load_session(args.session) if args.session else None,
                                backend=OllamaBackend(args.model), as_of=date.fromisoformat(args.as_of) if args.as_of else None)
        messages = json.loads(args.script.read_text(encoding='utf-8')) if args.script else [args.message] if args.message else None
        if messages is not None and (not isinstance(messages, list) or any(not isinstance(m, str) for m in messages)):
            raise ValueError('A script must be a JSON list of user-message strings.')
        if messages is None:
            print('Vehicle Consultation Agent. Use /reset to clear facts, /stop to cancel, /quit to exit.')
        failed = False
        while True:
            if messages is not None:
                if not messages:
                    break
                text = messages.pop(0)
                if not args.json:
                    print('You: ' + text)
            else:
                try:
                    text = input('You: ')
                except (EOFError, KeyboardInterrupt):
                    break
            if text.strip().lower() == '/quit':
                break
            answer = agent.handle(text)
            if args.session:
                save_session(agent.state, args.session)
            if args.json:
                print(json.dumps(answer, ensure_ascii=False, indent=2))
            else:
                print('Agent: ' + answer['message'])
                print('Status: ' + answer['status'] + '; executed tools: ' + ' -> '.join(e['name'] for e in answer['tools'] if e.get('executed')))
            if answer['status'] not in ('complete', 'needs_clarification', 'reset', 'cancelled'):
                failed = True
                if messages is not None:
                    break
        return 1 if failed else 0
    except (ValueError, OSError) as error:
        print('Could not start or save the consultation: ' + str(error))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
