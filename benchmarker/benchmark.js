const hive = require('@hiveio/hive-js')
const allOps = require('@hiveio/hive-js/lib/auth/serializer').makeBitMaskFilter(Array.from(Array(73).keys()))

const testArg = {
    user: 'techcoderx',
    queryObject: { tag: '', limit: 20 },
    queryFeed: { tag: 'techcoderx', limit: 20 },
    community: 'hive-196037',
    communityObject: { community: 'hive-196037' },
    accountObject: { account: 'techcoderx' }
}

const nodes = [
    'https://api.hive.blog',
    'https://api.openhive.network',
    'https://anyx.io',
    'https://hived.privex.io',
    'https://hived.hive-engine.com',
    'https://direct.hived.privex.io',
    'https://hiveseed-fin.privex.io',
    'https://hiveseed-se.privex.io',
    'https://fin.hive.3speak.online',
    'https://api.pharesim.me',
    'https://rpc.ausbit.dev',
    'https://rpc.ecency.com',
    'https://api.hivekings.com',
    'https://hive.roelandp.nl',
    'https://api.c0ff33a.uk',
    'https://api.deathwing.me',
    'https://hive-api.arcange.eu',
    'https://hived.emre.sh',
    'http://192.168.0.186:8093'
]

const suites = [
    // hived
    [null,'hived'],
    ['getDynamicGlobalProperties'],
    ['getConfig'],
    ['getChainProperties'],
    ['getVersion'],
    ['getHardforkVersion'],
    ['getBlock',38707240],
    ['getBlockHeader',38707240],
    ['getTransaction','e6352a698f5bfa5efc67bbd5e4cac27e960172ab'],
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
    ['getOpsInBlock',38707240,true],
    ['getWitnessCount'],
    ['getWitnessByAccount',testArg.user],
    ['getWitnessesByVote',-1,100],
    ['listProposals',[],10,'by_total_votes','ascending','votable'],
    ['listProposalVotes',[0],20,'by_proposal_voter','ascending','votable'],
    [1,'rc_api.find_rc_accounts',{ accounts: ["techcoderx"] }],
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
    ['getContent','techcoderx','techcoderx-is-officially-now-a-steem-witness'],
    ['getContentReplies','techcoderx','techcoderx-is-officially-now-a-steem-witness'],
    ['getRebloggedBy','techcoderx','techcoderx-is-officially-now-a-steem-witness'],
    ['getActiveVotes','techcoderx','techcoderx-is-officially-now-a-steem-witness'],

    // bridge
    [null,'bridge'],
    [1,'bridge.account_notifications',testArg.accountObject],
    [1,'bridge.unread_notifications',testArg.accountObject],
    [1,'bridge.get_community',{name:testArg.community,observer:testArg.user}],
    [1,'bridge.get_profile',testArg.accountObject],
    [1,'bridge.get_post',{author:testArg.user,permlink:'techcoderx-is-officially-now-a-steem-witness',observer:testArg.user}],
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
        results.push({rpc,total:cumulative,errors:errors})
        cumulative = 0
        errors = 0
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
results = []

console.log('\nWelcome to Hive RPC Benchmark')
runnodes(nodes,true,() => {
    results.sort((a,b) => a.total - b.total)
    console.log('Benchmark complete, results:')
    console.log(results)
    process.exit(0)
})