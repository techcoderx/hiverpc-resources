const nodes = require('./nodes')
const hive = require('@hiveio/hive-js')
const allOps = require('@hiveio/hive-js/lib/auth/serializer').makeBitMaskFilter(Array.from(Array(84).keys()))

const testArg = {
    block: 38707240,
    user: 'techcoderx',
    queryObject: { tag: '', limit: 20 },
    queryFeed: { tag: 'techcoderx', limit: 20 },
    community: 'hive-196037',
    communityObject: { community: 'hive-196037' },
    accountObject: { account: 'techcoderx' },
    post: { author: 'techcoderx', permlink: 'techcoderx-is-officially-now-a-steem-witness' },
    tx: 'e6352a698f5bfa5efc67bbd5e4cac27e960172ab'
}

const suites = [
    // hived
    [null,'hived'],
    ['getDynamicGlobalProperties'],
    ['getConfig'],
    ['getChainProperties'],
    ['getVersion'],
    ['getHardforkVersion'],
    ['getBlock',testArg.block],
    ['getBlockHeader',testArg.block],
    ['getTransaction',testArg.tx],
    ['getFeedHistory'],
    ['getCurrentMedianHistoryPrice'],
    ['getTicker'],
    ['getTradeHistory','2018-01-01T00:00:00','2018-01-02T00:00:00',5],
    ['getVolume'],
    ['getOrderBook',20],
    ['getRewardFund','post'],
    ['getAccounts',[testArg.user]],
    ['getVestingDelegations',testArg.user,'',5],
    ['getAccountHistory',testArg.user,-1,100,...allOps],
    ['getOpsInBlock',testArg.block,true],
    ['getWitnessCount'],
    ['getWitnessByAccount',testArg.user],
    ['getWitnessesByVote',-1,100],
    ['listProposals',[],10,'by_total_votes','ascending','votable'],
    ['listProposalVotes',[0],20,'by_proposal_voter','ascending','votable'],
    [1,'rc_api.find_rc_accounts',{ accounts: [testArg.user] }],
    [1,'rc_api.get_resource_params',{}],
    [1,'rc_api.get_resource_pool',{}],

    // hivemind
    [null,'hivemind'],
    ['getAccountReputations',testArg.user,1],
    ['getFollowers',testArg.user,'','blog',20],
    ['getFollowing',testArg.user,'','blog',20],
    ['getFollowCount',testArg.user],
    ['getTrendingTags','',20],
    ['getBlog',testArg.user,0,5],
    ['getBlogEntries',testArg.user,0,20],
    ['getDiscussionsByTrending',testArg.queryObject],
    ['getDiscussionsByHot',testArg.queryObject],
    ['getDiscussionsByCreated',testArg.queryObject],
    ['getDiscussionsByPromoted',testArg.queryObject],
    ['getDiscussionsByFeed',testArg.queryFeed],
    ['getDiscussionsByBlog',testArg.queryFeed],
    ['getPostDiscussionsByPayout',testArg.queryObject],
    ['getCommentDiscussionsByPayout',testArg.queryObject],
    ['getContent',testArg.post.author,testArg.post.permlink],
    ['getContentReplies',testArg.post.author,testArg.post.permlink],
    ['getRebloggedBy',testArg.post.author,testArg.post.permlink],
    ['getActiveVotes',testArg.post.author,testArg.post.permlink],

    // bridge
    [null,'bridge'],
    [1,'bridge.account_notifications',testArg.accountObject],
    [1,'bridge.unread_notifications',testArg.accountObject],
    [1,'bridge.get_community',{name:testArg.community,observer:testArg.user}],
    [1,'bridge.get_profile',testArg.accountObject],
    [1,'bridge.get_post',{author:testArg.post.author,permlink:testArg.post.permlink,observer:testArg.user}],
    [1,'bridge.get_account_posts',{account:testArg.user,sort:'blog'}],
    [1,'bridge.get_ranked_posts',{sort:'trending',tag:'',observer:testArg.user}],
    [1,'bridge.get_trending_topics',{}],
    [1,'bridge.list_community_roles',testArg.communityObject],
    [1,'bridge.list_all_subscriptions',testArg.accountObject],
    [1,'bridge.list_subscribers',testArg.communityObject],
    [1,'bridge.list_all_subscriptions',testArg.accountObject],
    [1,'bridge.list_communities',{}],
    [1,'bridge.list_community_roles',testArg.communityObject]
]

const runSuites = (suite,cb) => {
    let method = suites[suite][0]
    let outputKey = suites[suite][0]
    let params = suites[suite].slice(1)
    if (suites[suite][0] === null) {
        console.log('------------------------')
        console.log(suites[suite][1] + ' calls')
        console.log('------------------------')
        return runSuites(suite+1,cb)
    } else if (suites[suite][0] === 1) {
        method = 'call'
        outputKey = toCamel(params[0].split('.')[1])
    }
    hive.api[method](...params,(e) => {
        if (e) {
            console.log(e.toString())
            if (e.toString() == 'RPCError: Request Timeout')
                timeouts += 1
            else
                errors += 1
        }
        console.log(outputKey+': '+(new Date().getTime()-last_runtime)+'ms')
        cumulative += new Date().getTime()-last_runtime
        last_runtime = new Date().getTime()
        if (suite < suites.length-1)
            runSuites(suite+1,cb)
        else
            cb()
    })
}

const run = (rpc, appbase, cb) => {
    hive.api.setOptions({ url: rpc, useAppbaseApi: appbase })
    console.log('\nBenchmarking ' + rpc + '...')
    runSuites(0,() => {
        console.log('\nTotal benchmark time: ' + cumulative + 'ms\n')
        results.push({rpc,total:cumulative,errors:errors,timeouts:timeouts})
        cumulative = 0
        errors = 0
        timeouts = 0
        cb()
    })
}

const runnodes = (nodelst, appbase, cb) => {
    run(nodelst[0], appbase, () => {
        nodelst.shift()
        if (nodelst.length > 0)
            runnodes(nodelst, appbase, cb)
        else
            cb()
    })
}

const toCamel = (s) => {
    return s.replace(/([-_][a-z])/ig, ($1) => {
      return $1.toUpperCase()
        .replace('-', '')
        .replace('_', '')
    })
}

last_runtime = new Date().getTime()
cumulative = 0
errors = 0
timeouts = 0
results = []

console.log('\nWelcome to Hive RPC Benchmark')
runnodes(nodes,true,() => {
    results.sort((a,b) => a.total - b.total)
    console.log('Benchmark complete, results:')
    console.log(results)
    process.exit(0)
})