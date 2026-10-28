import os, io, secrets, hashlib
import pandas as pd
import streamlit as st
from supabase import create_client

st.set_page_config(page_title='All-State Player Rankings', page_icon='🏑', layout='centered')
st.title('🏑 All-State Player Rankings')

try:
    url=st.secrets['SUPABASE_URL']; key=st.secrets['SUPABASE_KEY']; admin_hash=st.secrets['ADMIN_PASSWORD_HASH']
    db=create_client(url,key)
except Exception:
    st.error('App is not configured yet. Follow README.md to add Supabase and Streamlit secrets.'); st.stop()

def admin_ok(password):
    return secrets.compare_digest(hashlib.sha256(password.encode()).hexdigest(),admin_hash)

def get_names():
    response=db.table('candidates').select('id,name').order('id').execute()
    return response.data or []

def parse_names(upload):
    data=upload.getvalue()
    if upload.name.lower().endswith('.csv'):
        df=pd.read_csv(io.BytesIO(data))
    else:
        df=pd.read_excel(io.BytesIO(data))
    if df.empty: return []
    preferred=next((c for c in df.columns if str(c).strip().lower() in ('name','player','player name','candidate')),df.columns[0])
    names=[str(x).strip() for x in df[preferred].dropna().tolist()]
    names=[n for n in names if n and n.lower()!='nan']
    if len(names)!=len(set(n.casefold() for n in names)):
        raise ValueError('Duplicate names found. Please make every name unique (for example, add a school).')
    return names

page=st.query_params.get('view','vote')
if page=='admin':
    st.subheader('Private organizer dashboard')
    pw=st.text_input('Admin password',type='password')
    if not pw: st.stop()
    if not admin_ok(pw): st.error('Incorrect password'); st.stop()
    settings=db.table('poll_settings').select('*').eq('id',1).single().execute().data
    candidates=get_names()
    st.write(f"Voting: **{'Open' if settings['is_open'] else 'Closed'}**")
    if st.button('Close voting' if settings['is_open'] else 'Reopen voting'):
        db.table('poll_settings').update({'is_open':not settings['is_open']}).eq('id',1).execute(); st.rerun()
    st.subheader('Upload candidate list')
    st.caption('Excel (.xlsx) or CSV. Use a Name column, or put names in the first column. Replacing names clears previous votes.')
    uploaded=st.file_uploader('Choose a spreadsheet',type=['csv','xlsx'])
    if uploaded:
        try:
            names=parse_names(uploaded)
            st.write(f'{len(names)} names detected')
            st.dataframe(pd.DataFrame({'Name':names}),hide_index=True)
            if st.checkbox('I understand replacing the list will permanently erase all previous votes'):
                if st.button('Replace candidate list',type='primary',disabled=not names):
                    db.rpc('replace_candidates',{'p_names':names}).execute(); st.success('List updated'); st.rerun()
        except Exception as e: st.error(str(e))
    st.subheader('Current results')
    ballots=db.table('ballots').select('id').execute().data or []
    votes=db.table('ballot_rankings').select('ballot_id,candidate_id,rank').execute().data or []
    st.metric('Submitted ballots',len(ballots))
    n=len(candidates)
    counts={c['id']:{'Name':c['name'],'Points':0,'First-place votes':0,'Total rankings':0} for c in candidates}
    for v in votes:
        if v['candidate_id'] in counts:
            item=counts[v['candidate_id']]
            item['Points']+=n-v['rank']+1
            item['First-place votes']+=int(v['rank']==1)
            item['Total rankings']+=1
    if counts:
        results=pd.DataFrame(counts.values()).sort_values(['Points','First-place votes','Name'],ascending=[False,False,True]).reset_index(drop=True)
        results.insert(0,'Position',range(1,len(results)+1))
        st.dataframe(results,hide_index=True,use_container_width=True)
        st.download_button('Download results CSV',results.to_csv(index=False).encode(),'all_state_results.csv','text/csv')
        st.caption('Scoring: with N players, 1st gets N points, 2nd N−1, and last gets 1. Ties in points are ordered by first-place votes; remaining ties are alphabetical for display only.')
    st.info('Share the main app URL without ?view=admin with voters. Keep your admin password secret.')
else:
    settings=db.table('poll_settings').select('is_open').eq('id',1).single().execute().data
    if not settings['is_open']:
        st.info('Voting is currently closed.'); st.stop()
    candidates=get_names()
    if not candidates:
        st.info('The organizer has not uploaded the player list yet.'); st.stop()
    st.write('Rank **every player** from #1 (highest) to last. Each player must receive a different rank. Voting is anonymous.')
    st.caption('You can select a rank for each player. All ranks must be used exactly once.')
    n=len(candidates)
    ranks={}
    with st.form('ballot'):
        for c in candidates:
            ranks[c['id']]=st.selectbox(c['name'],['Choose rank']+list(range(1,n+1)),key=f"rank_{c['id']}")
        submitted=st.form_submit_button('Submit anonymous ballot',type='primary')
    if submitted:
        selected=list(ranks.values())
        if 'Choose rank' in selected or set(selected)!=set(range(1,n+1)):
            st.error('Please assign every player a unique rank from 1 through '+str(n)+'.')
        else:
            try:
                db.rpc('submit_ballot',{'p_candidate_ids':[c['id'] for c in candidates], 'p_ranks':[int(ranks[c['id']]) for c in candidates]}).execute()
                st.success('Your anonymous ballot was submitted. Thank you!')
                st.balloons()
            except Exception:
                st.error('Your ballot could not be submitted. Voting may have closed or the player list changed. Refresh and try again.')
