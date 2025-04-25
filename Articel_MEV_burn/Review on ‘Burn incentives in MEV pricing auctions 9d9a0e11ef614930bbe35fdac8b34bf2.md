# Review on ‘Burn incentives in MEV pricing auctions’ and More

## Author

- **Name:** Mengzhong (Jeff) Ma
- **Email:** mamengzhong@gmail.com

See the original article: https://ethresear.ch/t/burn-incentives-in-mev-pricing-auctions/19856

While now the PBS solution is dominated by MEV sharing (MEV-share by Flashbots and MEV-blocker by CoW Swap), other solutions remain: MEV burning and MEV smoothing. The current solution employ relayers as the side-car to actualize the separation of proposer and builders, but this off-protocol design lays uncertainty to the ecosystem. In Ethereum roadmap, the Scourge stage introduces a in-protocol PBS (also,  enshrined PBS), which is expected to solve MEV issue by MEV burning. Similar with the case of MEV sharing, in the proposal design of MEV burning on ePBS, MEV value is estimated through an auction (MEV-pricing auction) among builders (or execution proposers) and then burned. At least one bid is expected in the auction that can cover some part of MEV. However, the incentives urging builders to place such bid may vary. The article https://ethresear.ch/t/burn-incentives-in-mev-pricing-auctions/19856 discusses the potential incentives that encourage builders’ bid in the MEV-pricing auction while analyzing each incentive’s sustainability. A take-away is that competition among Staking service providers (SSPs) will urge them to deprive each others’ profit by biding in the MEV-pricing auction, so as to prevent delegators switching to competitors. This spontaneous biding by the SSP related builders makes the public-good builder biding solely for the public goodwell unnecessary as long as new builders are free to entry. This article summarizes the necessary background for understanding EVM-burning and auction. As well, I give comments in the final section on the potential risk in the long-run which may drive the key assumption (builder market free entry) ineffective, which is ignored by the author.

# 1.  Background

Readers familiar with the current BPS setting and the previous discussion how to solve the issue of MEV can skip Section 1.1.

## 1.1 MEV Solutions

Mainly referred to : https://www.blocknative.com/blog/mev-smoothing-vs-burning

There are currently three main paths being explored for the future of MEV on Ethereum: burning, smoothing, and sharing. Burning and smoothing target the centralizing potential MEV can have on validators by either removing the economic incentives of MEV for validators altogether (burning) or by distributing the value of MEV evenly throughout the pool of active validators (smoothing) rather than to the single current proposing validator. MEV sharing, on the other hand, targets the redistribution of MEV back to the transaction originators rather than being burned or flowing downhill to validators. MEV sharing is also the only current solution to tackle the negative externalities of toxic forms of MEV such as sandwiches through order flow auctions (OFAs). 

### **1.1.1 MEV Burning**

Originally proposed by: https://ethresear.ch/t/burning-mev-through-block-proposer-auctions/14029

This proposal recommends implementing an auction for the “right to build a block” on the network. The auction would happen at the validator level. Instead of a single validator being selected to propose each block for each slot (the current configuration), this proposal would make it so that there are a select few validators that are all eligible to propose each slot. Which validator completes the task would then be selected based on auctioning off the “right to build a block”.

The theory presented in the original post is that each validator that is part of the proposal group will likely be willing to bid up to the amount of MEV reward included in the block for the right to propose the next block. This would result in the majority of the MEV being burned and validators only capturing the more consistent consensus and execution rewards for each block.

While the methodology outlined in domothy’s original post may not end up being the preferred method of MEV mitigation, it is worth mentioning that the official visual [Ethereum roadmap](https://www.blocknative.com/blog/ethereum-roadmap-guide) does mark “MEV burn” as a goal within the “Scourge” development path focusing on MEV:

![Screenshot 2024-06-20 at 1.46.28 PM.png](Review%20on%20%E2%80%98Burn%20incentives%20in%20MEV%20pricing%20auctions%209d9a0e11ef614930bbe35fdac8b34bf2/Screenshot_2024-06-20_at_1.46.28_PM.png)

### **1.1.2 MEV Smoothing**

Originally proposed by: https://ethresear.ch/t/committee-driven-mev-smoothing/10408

Additional materials: https://notes.ethereum.org/cA3EzpNvRBStk1JFLzW8qg

Author, Ethereum researcher [Francesco](https://twitter.com/fradamt), describes the proposal as such:

‘Smoothing MEV means reducing the variance in the MEV that is captured by each validator, with the ultimate goal of getting the distribution of rewards for each validator to be as close as possible to uniform: a staker would then get a share of rewards proportional to their stake, just like with issuance.’

The post argues in favor of a committee-driven approach to MEV smoothing where the proposer still receives some percentage of MEV rewards, but the rest is distributed amongst a committee of validators. Franceso describes the technical details in this manner:

“A validator gets assigned to one committee per epoch, and gets 1/6250 of the FlashBots bundles’ rewards for the corresponding block, if any. The proposed scheme leads to a fairly equitable distribution of rewards: the most unlucky get about 11% less than the luckiest, and most of the mass is concentrated in a much smaller range.”

The visuals included in the longer breakdown of this idea make the power of this proposal abundantly clear. Here you can see the estimated reward percentiles under the current market for validator MEV capture. The luckiest validators in the market outperform the majority of validators with 70% of all validators earning less than the mean:

![Untitled](Review%20on%20%E2%80%98Burn%20incentives%20in%20MEV%20pricing%20auctions%209d9a0e11ef614930bbe35fdac8b34bf2/Untitled.png)

Under an MEV smoothing structure, the rewards distribution would likely be much more predictable and fairly distributed:

![Untitled](Review%20on%20%E2%80%98Burn%20incentives%20in%20MEV%20pricing%20auctions%209d9a0e11ef614930bbe35fdac8b34bf2/Untitled%201.png)

Adding MEV smoothing as proposed above [would require](https://www.jvillella.com/mev-smoothing) an update to Ethereum’s [attestation](https://ethereum.org/en/developers/docs/consensus-mechanisms/pos/attestations/) and [fork choice](https://ethereum.org/en/developers/docs/consensus-mechanisms/pos/gasper/) rules. Similar to the timeline for any proposed MEV burning initiatives, enshrining these rule changes within the protocol would likely take years.

### **1.1.3 MEV Sharing**

### [**MEV Blocker**](https://mevblocker.io/)

An OFA introduced by the CoW Swap / Gnosis / Agnostic teams to solve two main problems: 1) aggregate the fragmented blockspace market across many builders and 2) provide a system that refunds or rebates the MEV the transaction creates back to the transaction originator. As of August, 2023, MEV Blocker has been extremely successful in sending transactions privately with over [5.5MM successful private transactions](https://dune.com/cowprotocol/mev-blocker), while MEV refunds have been a little slower to gain adoption. MEV Blocker has processed about ~8,000 refunds totaling 370ETH.

### [**MEV-Share**](https://docs.flashbots.net/flashbots-protect/mev-share)

An OFA introduced by Flashbots that also rebates value derived from MEV back to the transaction originator, however their focus is more on user-privacy. With MEV Blocker, they will share all of the transaction details (except the signature of course!) to searchers who bid for the 
right to backrun the transaction and rebate the transaction originator. Flashbot’s MEV-Share, on the other hand, gives users the option to reveal some, all, or none of the transaction details. This makes it harder for searchers to backrun the transaction, but provides more privacy guarantees to the transaction originator. As of August, 2023, MEV-Share has facilitated [3.2MM private transactions](https://docs.flashbots.net/flashbots-mev-share/searchers/event-stream#get-apiv1historyinfo). MEV rebate data is not yet publicly available.

## 1.2 Enshrined PBS (or *in-protocol/IP PBS)*

Reference: https://ethresear.ch/t/why-enshrine-proposer-builder-separation-a-viable-path-to-epbs/15710

Enshrined PBS (ePBS) advocates for implementing PBS into the [consensus layer](https://github.com/ethereum/consensus-specs/tree/dev)  of the Ethereum protocol. Because there was no in-protocol solution at the time of the merge, [Flashbots](https://www.flashbots.net/) built [`mev-boost`](https://github.com/flashbots/mev-boost) , which became a massively adopted out-of-protocol solution for PBS that accounts for ≈90% of Ethereum blocks produced.

While there are [many](https://github.com/michaelneuder/mev-bibliography#specific-proposals) proposed ePBS implementations, here I present a small modification of the original [two-slot](https://ethresear.ch/t/two-slot-proposer-builder-separation/10980) design from Vitalik. We call it Two-Block HeadLock (TBHL) because it uses a single slot to produce two blocks. The first is a proposer block that contains a commitment to a specific execution payload and the second is a builder block that contains the actual transaction contents (here we just call the overall pair of blocks a “single” slot because only one execution payload is produced).

TBHL has the notion of *proposer* and *builder* blocks. Each slot can contain at most: one proposer block + one builder block, each of which receives attestations. The slot duration is divided into 4 periods:

- t=t0 : **The proposer chooses winning bid and publishes a proposer block.**
    
    The proposer starts by observing the bidpool, which is a p2p topic where builders send their bids. The proposer selects one of these bids and includes it in a block they publish before t1.
    
- t=t1 : **The attesting committee for the proposer block observes for a timely proposal.**
    
    This is the equivalent of the “attestation deadline” at t=4 in the current mechanism. If at least one block is seen, the attesting committee votes for the first one that they saw. If no block is observed, the attesting committee votes for an empty slot (this requires[`block, slot`](https://github.com/ethereum/consensus-specs/pull/2197) voting).
    
- t=t1.5 : **The attesting committee for the builder block checks for equivocations.**
    
    If the attesting committee sees (i) more than one proposer block or (ii) no proposer blocks, they give no proposer boost to any subsequent builder block. If the attesting committee sees a unique proposer block, they give proposer boost to the builder associated with that bid (see [“*Headlock in ePBS*”](https://ethresear.ch/t/equivocation-attacks-in-mev-boost-and-epbs/15338#headlock-in-epbs-8) for more details).
    
- t=t2 : **The builder checks if they are the unique winner.**
    
    If a builder sees an equivocation, they produce a block that includes the equivocation as proof that their unconditional payment should be reverted. Otherwise, the builder can safely publish their builder block with a payload (the transaction contents). If the builder *does not* see the proposer block as the head of the chain, they publish an empty block extending their head (see[“*Headlock in ePBS*”](https://ethresear.ch/t/equivocation-attacks-in-mev-boost-and-epbs/15338#headlock-in-epbs-8) for more details).
    
- t=t3 : **The attesting committee for the builder block observes for a timely proposal.**
    
    This is a round of attestations that vote for the builder block. This makes t3 a second attestation deadline.
    

![Fig.1. *The slot anatomy of TBHL. A proposer block is proposed and attested to in the purple phase, while a builder block is proposed and attested to in the yellow phase. The proposers, attesters, and builders each make different observations at various timestamps in the slot.*](Review%20on%20%E2%80%98Burn%20incentives%20in%20MEV%20pricing%20auctions%209d9a0e11ef614930bbe35fdac8b34bf2/Untitled%202.png)

Fig.1. *The slot anatomy of TBHL. A proposer block is proposed and attested to in the purple phase, while a builder block is proposed and attested to in the yellow phase. The proposers, attesters, and builders each make different observations at various timestamps in the slot.*

## 1.3 MEV Solutions based on ePBS

### **1.3.1 MEV burn add-on to enshrined PBS (block auction)**

MEV burn is a simple add-on to enshrined PBS.

- **payload base fee**: Bids specify a payload base fee no larger than the builder balance minus the payload tip.
- **payload base fee burn**: The payload base fee is burned, even if the payload is invalid or revealed late.
- **payload base fee floor**: During the bid selection attesters impose a subjective floor on the payload base fee.
    - *subjective floor*: Honest attesters set their payload base fee
    floor to the top builder base fee observed D seconds (e.g. D = 2) prior
    to the time honest proposers propose (**attesters observation deadline**).
    - *synchrony assumption*: D is a protocol parameter greater than the bid gossip delay.
- **payload base fee maximisation**: Honest proposers select winning bids that maximise the payload base fee.

![Untitled](Review%20on%20%E2%80%98Burn%20incentives%20in%20MEV%20pricing%20auctions%209d9a0e11ef614930bbe35fdac8b34bf2/Untitled%203.png)

ePBS without MEV burn incentivizes builders to compete for the largest builder balance (*payload tip should be* no larger than the builder balance). Indeed, for exceptionally large MEV spikes the most capitalised builder has the power to capture all MEV above the second-largest builder balance. This design flaw can be patched with a L1 zkEVM that provides post-execution proofs.

### 1.3.2 A Change in the Market Structure (slot auction)

ePBS enshrines both a specific market structure and an allocation mechanism mostly inherited from MEV-Boost. The idea of MEV-Boost is: A validator (or beacon proposer) is given *proposing* *rights* allowing them to propose an execution payload once their turn is up, and receive proceeds from the use of these rights. Proposers sell off their *whole* payloads, and builders *commit* to payload contents at the time of the bid. At this point, it allows and requires the *validator* remain the payload *proposer.*

There are discussions and comments on why and whether we need to separate beacon proposer and payload proposer (see https://mirror.xyz/barnabe.eth/LJUb_TpANS0VWi3TOwGx_fgomBvqPaQ39anVj3mnCOg). Here I numerate two reasons to do so:

1. [**Timing games](https://arxiv.org/abs/2305.09032)** occur when a proposer delays as much as possible the proposing of their block in order to obtain more value for it. In block-auction ePBS, as the execution payloads are determined at the release of the beacon block, the timing games will be played by validators who will attempt to delay the release of the beacon block as much as possible to commit to bids of higher value.  
2. In the *validator-as-proposer* model, one may consider the validator to be a passive monopolist, who simply listens to bids made by builders for the right to build the payload. In the *validator-proposer-separation* model, as performed by ETs (https://ethresear.ch/t/execution-tickets/17944?u=barnabe) for instance, the ticket holder would become an *active monopolist*, who according to Quintus and Conor “cannot be circumvented and is thus able to do things like establish minimum tips that transactions have to pay to be included in their block(s) ([monopoly pricing](https://arxiv.org/abs/2311.12731)) and frontrun time-sensitive flow with little concern for recourse.”

The following figure illustrate the validator-proposer-separation: 

![Screenshot 2024-06-21 at 4.31.01 PM.png](Review%20on%20%E2%80%98Burn%20incentives%20in%20MEV%20pricing%20auctions%209d9a0e11ef614930bbe35fdac8b34bf2/Screenshot_2024-06-21_at_4.31.01_PM.png)

With validator-proposer-separation, we still need some isolation measures to avoid centralization of validators. Because of MEV, there are large incentives for validators to outsource the execution payload construction to an external market of builders. This reality continues to place centralizing pressure on the validator set, as vertical integration, colocation, and pooling directly translate to more rewards.  Say, it is a dominant strategy for the beacon proposer to commit to themselves as execution proposer to grasp MEV value. Therefore, two methods are proposed to figure out this issue: Execution Tickets and Execution Auctions, both of which include burning MEV. 

**1.3.2.1 Execution Tickets** (https://ethresear.ch/t/execution-tickets/17944/1)

ETs allow execution proposers to go to a market where they purchase “tickets” redeeming execution proposing rights at some indeterminate time into the future, as shown in the figure below:

![Screenshot 2024-06-21 at 4.35.38 PM.png](Review%20on%20%E2%80%98Burn%20incentives%20in%20MEV%20pricing%20auctions%209d9a0e11ef614930bbe35fdac8b34bf2/Screenshot_2024-06-21_at_4.35.38_PM.png)

The basic flow for one slot is:

1. During the **beacon round**, the randomly selected **beacon proposer** has authorization to propose a **beacon block**.
2. This proposer proposes the **beacon block** that contains the **inclusion list**.
3. The **beacon attesters** vote on the validity and timeliness of the **beacon block**.
4. During the **execution round**, a randomly selected **execution ticket** has authorization to propose an **execution block**.
5. The owner of the ticket is the **execution proposer** and proposes an **execution block**.
6. The **execution attesters** vote for on the timeliness and validity of the **execution block**.

In the end, the burning mechanism in the execution ticket design is more straightforward
 – you simply burn the full price of the ticket.

**1.3.2.1 Execution Auctions (f.k.a. APS-Burn)**

Recall the design of MEV burn add-on to ePBS, which burns payload base fee from the builder winning the bids, the design of Execution Auction involve the auctioning off the rights to the entire slot in advance to the Payload Proposer. The beacon proposer of slot *N* decide which bid to commit to, where the bids are made for the execution proposing rights of slot *N*+32. 

![Screenshot 2024-06-21 at 5.29.23 PM.png](Review%20on%20%E2%80%98Burn%20incentives%20in%20MEV%20pricing%20auctions%209d9a0e11ef614930bbe35fdac8b34bf2/Screenshot_2024-06-21_at_5.29.23_PM.png)

In this case, fee from the bid winner will be burned.

# 2. Burn Incentives in MEV Pricing Auctions

The above discussed MEV burning design all need at least one builder (in section 1.3.1) or execution proposer (in section 1.3.2) give a bid that is high enough to cover some MEV, before the attesters observation deadline. If builders bid before the observation deadline with the same timing as today, then the mechanism will burn substantial MEV. However, things could change as builders and proposers may collude to avoid giving high bid before the attesters observation deadline to as to retain MEV, lacking the incentive to burn MEV. A modified MEV pricing auction, [MEV burn with builder kickbacks](https://ethresear.ch/t/mev-burn-incentivizing-earlier-bidding-in-a-simple-design/17389), attempts to compensate builders for bidding early, but is there any spontaneous incentives from the builders or proposers? https://ethresear.ch/t/burn-incentives-in-mev-pricing-auctions/19856 discussed several incentives that can urge bid for MEV pricing auction, and competition among Staking service providers (SSPs) could even resulting in burning large amount of MEV without any outside incentives.

## 2.1 Public Goods Builder

Firstly we regard burning MEV as a public good and discuss the possibility that if Ethereum’s users believe that burning MEV is a public good, they may come together to fund the development and operation of a public good builder. 

### 2.1.1 **(A) Non-profit Public good builder**

The first example is a builder that dedicates resources to burning MEV without a direct profit motive. Initiatives to fund public goods are fairly [prevalent](https://medium.com/ethereum-optimism/retroactive-public-goods-funding-33c9b7d00f0c) within the Ethereum ecosystem. The public good builder can for example consistently bid according to guaranteed MEV at the observation deadline in the block auction design. This ensures that the MEV is burned while 
the builder will not suffer any direct losses from the bid. In the slot auction design, the builder would instead need to bid according to its expected MEV for the entire slot and might bid slightly below to stay safe. The builder may by supported any public goods funding received diligently and not strive for any profit.

### 2.1.2 (B) For-profit public good builder

A builder that positions itself as providing a public good may also enjoy direct economic benefits from its operation if some validators sympathize with the mission. There may for example be a market fit for builders that do not censor, nor extract various types of toxic MEV. In the block auction design, the builder could keep the MEV base fee in line with the available (non-censorship/non-toxic) MEV during the attester auction, and then pivot to tipping afterward, retaining some small profit margin. The MEV in some blocks is not particularly geared towards specialized searchers, and stakers may not lose that much in tips for some blocks by selecting the public good builder. Therefore, the public good builder could have higher profit margins in the blocks it does eventually get to build than builders that have not positioned themselves as providing a public good. A builder bidding before the observation deadline might of course also hope that its bids are the only ones to reach the proposer in times of degraded network conditions.

Hoping public good builders sustain honestly biding only out of public wellfare sounds good but cannot be sustained over the long run. Many stakers will not be particularly enthusiastic over a builder that burns their MEV opportunities, and the finally the situation deviate to the equilibrium that the public good builder could commit to burning the maximum possible MEV but abstain from doing so as it receives a bribe from the proposer. However, if builders-proposers is a free entry market, a sole profitable builder will attract a few more to enter the market as well. There is not much use in paying off two builders if it turns out that a third burned the MEV anyway through a bid. A mechanism for reconciling this ex-post would become rather complex. The validator may then be better off by simply not negotiating with any extortion builder.

While collusion between builders and proposers seems unsustainable, it helps to underscore the power that builders have over proposers. The ultimate incentive for burning MEV then emerges when changing the responsible actor from builder to stakers.

## **2.2 (D) Staker-initiated Griefing**

Staking service providers (SSPs) compete for delegated stake and derive income by taking a cut of the staking yield when they pass it back to the delegators. An SSP must ensure that the yield it offers delegating stakers is competitive relative to offers from other SSPs. The MEV pricing auction may therefore lead SSPs to burn competing proposers’ MEV by tightly integrating with builders or running them in-house. If a competitor burns an SSP’s MEV, then the SSP must respond in kind or will lose out on delegators and thus income. When considering the metalevel of SSPs, this equilibrium seems more stable than an equilibrium of late bidding leading to little or no MEV burn. All it takes to break the late-bidding cartel is one defecting SSP builder, forcing others to respond.

An SSP that through a builder griefs other stakers without taking any loss executes something comparable to a [discouragement attack](https://github.com/ethereum/research/blob/d1d465f658e0024a2010b0a6ad960a76d9c40cac/papers/discouragement/discouragement.pdf) with an infinite griefing factor. This is a very advantageous attack, primarily because delegators will flow to the best performing SSP. In 
addition, a reduction in overall yield for other stakers pushes down the quantity of supplied stake, bringing up the equilibrium yield. Thus, even if some delegators do not flow to the SSP that burns its competitor’s MEV, the expected staking yield (that the SSP will share in
 the profit from) will still go up, if the competitor’s customers simply stop delegating. Of course, the cost of running the builder must be accounted for. But large SSPs can amortize that cost across a vast amount of yield-bearing validators.

Yet, directly profiting from the MEV is almost always better than burning it. When an SSP’s builder is able to extract more MEV in a competitor’s slot than any other builder, it will still be better off only bidding to a level that ensures it wins the auction. The SSP must thus make a probabilistic judgment as to the uniqueness of its MEV opportunity in the particular slot before deciding how to proceed (or more precisely, any edge in MEV value $V_e$ relative to the second best builder). An SSP builder must in essence bid before the observation deadline up to the point where the expected payoff from burning the marginal MEV is equal to the expected payoff 
from waiting and hoping to extract it. The point is to assert that there are stronger incentives for builders to bid before the observation deadline than what has been previously understood, because a builder might be run by an SSP that indirectly profits from burning other stakers’ potential MEV revenue.

### 2.2.1 (E) Metagame—staker-initiated griefing cartel

In such a competition among SSPs, another question rises. Can builders operating at the metalevel collude to selectively burn or selectively *not* burn MEV, depending on the identity of the slot’s validator? The cartel would strive to ensure that all participating SSPs (or any union of 
solo stakers) receive the MEV in their validators’ proposed blocks, while minimizing MEV in all other validators’ blocks.

However, if attesters are honest, builders can only cartelize to selectively burn or not burn MEV that they uniquely are able to extract. As long as competing builders are operational, this substantially limits the power of any cartel. Therefore, the advantage of (E) over (D) is not substantial.

**2.2.1.1 Proposer is part of the cartel**

When the beacon proposer is part of the cartel, members will abstain from bidding before the observation deadline to ensure that as much value as possible flows to the proposer. This type of cartelization has been highlighted as a concern ([1](https://ethresear.ch/t/mev-burn-a-simple-design/15590/4), [2](https://ethresear.ch/t/dr-changestuff-or-how-i-learned-to-stop-worrying-and-love-mev-burn/17384/3)) in the debate around MEV pricing auctions. The idea is that participants come to an explicit or implicit agreement to not bid before
 the observation deadline. Yet the incentive to burn MEV is stronger than previously understood, since stakers outside the cartel will wish to grief cartel members by bidding early (D), and so from this perspective, the risk of late-bidding-cartelization is lower than feared.

It might also be difficult to efficiently uphold cartelization, because it is not possible for members to know which, if any, defected in pursuit of (D). One avenue would be to try to share the profits from every slot to give all participants incentives to hold back bids before the observation deadline. Yet overall, the existence of (A), (B), and (D) means that some value will still reasonably be burned by public good builders or any competitors not part of the cartel.

**2.2.1.2 Proposer is not part of the cartel**

When the beacon proposer is outside the cartel, the goal is to deprive it of revenue while still capturing as much of the MEV as possible. It will still be more profitable for the cartel to extract any unique MEV opportunity rather than burn it. Define $V_s$ as the value a builder can attain in the slot auction and $V_b$ as its value for the block auction (from a block built at the observation deadline). When a builder can extract the most MEV, it has an edge $V_e$ over the second-best builder (kept constant for simplicity). Just as in (D), the cartel can bid up to $V_b−V_e$ or $V_s−V_e$, with the difference that $V_e$ expands if the cartel collectively gains a larger edge against the best
 builder outside of the cartel. This expansion is what the cartel tries to capitalize on, both when the proposer is part of the cartel (expanding $V_e$ to lower the burn) and when not (expanding $V_e$ to increase builder profits). A challenge—just as in (D)—is that the cartel might not be able to properly estimate $V_e$. After the observation deadline, the cartel attempts to extract as much 
value as possible, leaving the MEV either burned or in their hands.

In the original article, the author also discusses the potential Risks associated with attester–builder integration as well as the difference derived by Block vs. slot auctions. While his main conclusion, i.e., burning in (D), still holds, I restrain to repeat those discussions here.

# 3. Comments

While the spontaneous EVM-pricing biding driven by competition among SSPs seems charming, it depends on a pivotal assumption, which is free market entry by builders. Collusion among builders with proposers also cannot impede effective bids on MEV auction as there will be griefing from new entrants. However, in the long-run, this conclusion may fail due to the ineffectiveness of market free entry, which is caused by consistently failing to profit for those late-coming builders.

As discussed in Section 2.2, SSPs are incentivized to cartel both horizontally and vertically, or even bought out by one entity. This trend, together with relatively large capital needed to be a validator, makes large SSP cartel the natural monopoly, which enjoys economies of scale. This economies of scale, in terms of MEV, means the decreasing average cost per unit of MEV profit grasped by the builder-SSP entity as the entity becomes larger and larger. This relatively lower cost can be derived from better algorithm, lower energy cost per unit, and more efficient management as the entity goes large. Meanwhile, this lower cost also gives the entity advantage against new entries that the entity can still profit on MEV with high bid in the MEV auction, in which case new entries cannot profit or even loss. In the end, the builder market is inefficient as free to entry. Although new builders are free to enter, they are unable to profit while stay, finally being crowded out. 

While this inefficiency seems disappointing, whether monopoly could actually be formed should be studies in a more stringent manner. The current market amounts to oligopoly while several forces exist to prevent it to be monopoly, a super-centralized state. Therefore, if all the discussions above are correct, we still need to know to which degree of oligopoly the effect of economies of scale would curb new entrants while worse off the situation.