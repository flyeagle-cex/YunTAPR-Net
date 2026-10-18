"""No start/resume/reconcile-ledger flags; inspect or append a new observation."""
import argparse,json
from .review import run

def main():
    parser=argparse.ArgumentParser(description='Read-only stopped-session review; no training capability')
    parser.add_argument('--campaign',default=None,help='Exact registered stopped campaign name')
    parser.add_argument('--record',action='store_true',help='Write separate append-only postmortem receipt')
    args=parser.parse_args();result=run(args.campaign,args.record)
    print(json.dumps(result,indent=2,ensure_ascii=False))
    return 2 if result.get('status')=='NOT_VERIFIED' else 0
if __name__=='__main__':raise SystemExit(main())
