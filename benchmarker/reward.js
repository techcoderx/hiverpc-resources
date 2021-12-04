const hive = require('@hiveio/hive-js')
const producer_reward_op = require('@hiveio/hive-js/lib/auth/serializer').makeBitMaskFilter([require('@hiveio/hive-js/lib/auth/serializer/src/ChainTypes').operations.producer_reward])
const witness = process.argv[2]
const days = parseInt(process.argv[3])

if (!witness || witness === '--help' || witness === '-help' || witness === '-h' || isNaN(days)) {
    console.log('Usage: node reward.js <witness> <days>')
    process.exit(0)
}

const currentTs = new Date().getTime()
const durationMs = 1000*60*60*24*(days)

const getProducerRewards = (last, cb, total = 0, count = 0) => {
    hive.api.getAccountHistory(witness,last,1000,...producer_reward_op,(e,h) => {
        if (e) {
            console.log(e)
            return cb(Math.round(total*1000000)/1000000,count)
        } else
            console.log('fetched',h.length,'ops')
        for (let i = h.length - 1; i >= 0; i--)
            if ((currentTs - durationMs) < new Date(h[i][1].timestamp).getTime()) {
                total += parseFloat(h[0][1].op[1].vesting_shares)
                count++
            }
        if ((currentTs - durationMs) < new Date(h[0][1].timestamp).getTime())
            getProducerRewards(h[0][0]-1,cb,total,count)
        else
            cb(Math.round(total*1000000)/1000000,count)
    })
}

getProducerRewards(-1,(vestProduced,count) => {
    console.log('Blocks Produced:',count)
    console.log('Vests Produced:',vestProduced)
    hive.api.getDynamicGlobalProperties((e,props) => {
        if (e)
            console.log(e)
        else
            console.log(hive.formatter.vestToHive(vestProduced,props.total_vesting_shares,props.total_vesting_fund_hive),'HIVE')
    })
})