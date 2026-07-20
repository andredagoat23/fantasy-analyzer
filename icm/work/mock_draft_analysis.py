# Grade the user's mock draft ("Like a good..." team, slot 7 of 12) against the live board.
# Full 192-pick order reconstructed from screenshots; DSTs skipped (not on board).
import sys
import pandas as pd
import numpy as np
sys.path.insert(0, ".")
from utils import normalize_name

vb = pd.read_csv("value_board.csv")
vb["nn"] = vb["full_name"].apply(normalize_name)
vb["pos"] = vb["pos_label"].str.extract(r"([A-Z]+)")

# ordered pick list (name, is_user_pick). DST entries = None placeholders to keep pick numbers right.
R = lambda names: names
picks = []
rounds = [
 R(["Jahmyr Gibbs","Bijan Robinson","Puka Nacua","Christian McCaffrey","Ja'Marr Chase","Amon-Ra St. Brown","Jaxon Smith-Njigba","Jonathan Taylor","CeeDee Lamb","De'Von Achane","James Cook","Ashton Jeanty"]),
 R(["Rashee Rice","Jeremiyah Love","Drake London","Derrick Henry","Justin Jefferson","Trey McBride","Saquon Barkley","Malik Nabers","Omarion Hampton","Josh Jacobs","Nico Collins","Chris Olave"]),
 R(["Brock Bowers","Breece Hall","A.J. Brown","George Pickens","Chase Brown","Kenneth Walker","Josh Allen","Garrett Wilson","DeVonta Smith","Javonte Williams","Kyren Williams","Tetairoa McMillan"]),
 R(["Zay Flowers","Tee Higgins","Travis Etienne","Cam Skattebo","Bucky Irving","D'Andre Swift","Terry McLaurin","Carnell Tate","Davante Adams","Colston Loveland","Quinshon Judkins","Emeka Egbuka"]),
 R(["TreVeyon Henderson","Lamar Jackson","Ladd McConkey","Jameson Williams","Jadarian Price","Jaylen Waddle","David Montgomery","Luther Burden","Tyler Warren","DJ Moore","Jayden Daniels","Bhayshul Tuten"]),
 R(["Harold Fannin","Marvin Harrison","Drake Maye","Michael Pittman","Jalen Hurts","Mike Evans","Joe Burrow","Kyle Pitts","Sam LaPorta","Chuba Hubbard","Alec Pierce","Rome Odunze"]),
 R(["Jaxson Dart","Tony Pollard","Jordyn Tyson","Courtland Sutton","Brian Thomas","Travis Kelce","Rico Dowdle","DK Metcalf","Christian Watson","Aaron Jones","Jaylen Warren","Chris Godwin"]),
 R(["Parker Washington","Wan'Dale Robinson","Jakobi Meyers","Brock Purdy","Rachaad White","J.K. Dobbins","Makai Lemon","Dak Prescott","Travis Hunter","Kenny Gainwell","George Kittle","Rhamondre Stevenson"]),
 R(["Ricky Pearsall","Matthew Golden","RJ Harvey","Trevor Lawrence","Michael Wilson","KC Concepcion","Josh Downs","Dallas Goedert","Kyle Monangai","Jake Ferguson","Tucker Kraft","Caleb Williams"]),
 R(["Jordan Addison","Xavier Worthy","Blake Corum","Jonathon Brooks","Quentin Johnston","Khalil Shakir","Brandon Aubrey","Tyjae Spears",None,"Bo Nix",None,"Jacory Croskey-Merritt"]),
 R(["Woody Marks","Romeo Doubs",None,"Alvin Kamara","Jayden Reed","Jalen Coker","Zach Charbonnet",None,"Cameron Dicker",None,None,None]),
 R(["Isiah Pacheco","Ka'imi Fairbairn","Jason Myers",None,"Omar Cooper","Tyler Shough","Jalen McMillan","Harrison Mevis","Jordan Mason","Jayden Higgins","Eddy Pineiro","Cam Little"]),
 R(["Chris Rodriguez","Isaiah Likely","Jake Bates","Calvin Ridley",None,None,"Harrison Butker","Patrick Mahomes","Tyler Allgeier","Jerry Jeudy","Tank Bigsby","Tyler Loop"]),
 R(["Justin Herbert","Matthew Stafford","Brian Robinson","T.J. Hockenson","Cairo Santos","Tre Tucker","Rashid Shaheed","Braelon Allen","Will Reichard","Jauan Jennings","Germie Bernard",None]),
 R(["Chris Bell","Kenyon Sadiq","Mark Andrews","Dalton Kincaid","Kyler Murray","Daniel Jones",None,"Darnell Mooney","Denzel Boston","Chris Boswell","Antonio Williams","James Conner"]),
 R(["Stefon Diggs",None,"Jalen Nailor","Tyrone Tracy","Mike Washington","Hunter Henry","Malik Willis","Jared Goff","Baker Mayfield","Adonai Mitchell","Ray Davis","Terrance Ferguson"]),
]
USER_SLOTS = {1:7, 2:6, 3:7, 4:6, 5:7, 6:6, 7:7, 8:6, 9:7, 10:6, 11:7, 12:6, 13:7, 14:6, 15:7, 16:6}

flat = []
for rnd, names in enumerate(rounds, 1):
    for i, nm in enumerate(names, 1):
        flat.append({"pick": (rnd-1)*12 + i, "round": rnd, "slot": i, "name": nm,
                     "user": USER_SLOTS[rnd] == i})

fp = pd.DataFrame(flat)
fp["nn"] = fp["name"].apply(lambda n: normalize_name(n) if n else None)
board = vb.set_index("nn")
fp["found"] = fp["nn"].isin(board.index)
unmatched = fp[fp["name"].notna() & ~fp["found"]]["name"].tolist()
print("unmatched (ok if deep sleepers/DST):", unmatched, "\n")

def bd(nn, col):
    return board.at[nn, col] if nn in board.index else np.nan

fp["comp"] = fp["nn"].map(lambda n: bd(n, "rank_composite") if n else np.nan)

print("=== YOUR PICKS, graded ===")
print(f"{'pk':>3} {'player':22} {'pos':6} {'board#':>6} {'value':>6}  {'bust':>5} {'floor':>5} {'ceil':>5}   best still on board (by composite)")
for _, r in fp[fp.user].iterrows():
    if not r["found"]:
        print(f"{r['pick']:>3} {r['name'] or 'D/ST':22} {'':6} {'--':>6} {'--':>6}")
        continue
    taken = set(fp[fp["pick"] < r["pick"]]["nn"].dropna())
    avail = vb[~vb["nn"].isin(taken) & (vb["nn"] != r["nn"]) & vb["pos"].isin(["QB","RB","WR","TE"])]
    top3 = avail.nsmallest(3, "rank_composite")
    alts = ", ".join(f"{a.full_name} (#{a.rank_composite:.0f})" for _, a in top3.iterrows())
    val = r["pick"] - r["comp"]
    print(f"{r['pick']:>3} {r['name']:22} {bd(r['nn'],'pos_label'):6} {r['comp']:>6.0f} {val:>+6.0f}  "
          f"{bd(r['nn'],'p_bust')*100:>4.0f}% {bd(r['nn'],'floor'):>5.0f} {bd(r['nn'],'ceiling'):>5.0f}   {alts}")

# team risk profile: projected starters (QB 2RB 2WR TE FLEX K)
mine = fp[fp.user & fp.found].copy()
mine = mine.merge(vb, on="nn")
starters = []
for pos, k in [("QB",1), ("RB",2), ("WR",2), ("TE",1)]:
    starters += mine[mine["pos"]==pos].nsmallest(k, "rank_composite")["nn"].tolist()
flex_pool = mine[mine["pos"].isin(["RB","WR","TE"]) & ~mine["nn"].isin(starters)]
starters += flex_pool.nsmallest(1, "rank_composite")["nn"].tolist()
st = mine[mine["nn"].isin(starters)]
print(f"\n=== STARTING LINEUP RISK PROFILE (QB/2RB/2WR/TE/FLEX) ===")
print(f"combined proj {st['total_points'].sum():.0f} | floor {st['floor'].sum():.0f} | ceiling {st['ceiling'].sum():.0f}")
print(f"avg bust {st['p_bust'].mean()*100:.0f}% | starters with bust>35%: "
      f"{', '.join(st[st['p_bust']>0.35]['full_name_x' if 'full_name_x' in st.columns else 'full_name'])}")
