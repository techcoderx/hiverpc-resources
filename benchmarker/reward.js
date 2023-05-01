const hive = require('@hiveio/hive-js')
const producer_reward_op = require('@hiveio/hive-js/lib/auth/serializer').makeBitMaskFilter([require('@hiveio/hive-js/lib/auth/serializer/src/ChainTypes').operations.producer_reward])
const witness = process.argv[2]
const days = parseInt(process.argv[3])
const printByDate = process.argv[4] === 'true'

hive.api.setOptions({ url: 'https://techcoderx.com' })

if (!witness || witness === '--help' || witness === '-help' || witness === '-h' || isNaN(days)) {
    console.log('Usage: node reward.js <witness> <days>')
    process.exit(0)
}

const currentTs = new Date().getTime()
const durationMs = 1000*60*60*24*(days)

const constructDayMap = () => {
    let dayMap = {}
    
    for (let i = 1; i <= 12; i++) {
        dayMap[i] = {}
        for (let j = 1; j <= 31; j++)
            dayMap[i][j] = 0
    }
    return dayMap
}

let yearMap = {}

const getProducerRewards = (last, cb, total = 0, count = 0) => {
    hive.api.getAccountHistory(witness,last,1000,...producer_reward_op,(e,h) => {
        if (e) {
            console.log(e)
            return cb(Math.round(total*1000000)/1000000,count)
        } else
            console.log('fetched',h.length,'ops')
        for (let i = h.length - 1; i >= 0; i--) {
            let date = new Date(h[i][1].timestamp)
            if ((currentTs - durationMs) < date.getTime()) {
                total += parseFloat(h[0][1].op[1].vesting_shares)
                count++
                if (!yearMap[date.getFullYear()]) {
                    yearMap[date.getFullYear()] = constructDayMap()
                }
                yearMap[date.getFullYear()][date.getMonth()+1][date.getDate()] += parseFloat(h[0][1].op[1].vesting_shares)
            }
        }
        if (h.length > 0 && (currentTs - durationMs) < new Date(h[0][1].timestamp).getTime())
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
        if (printByDate)
            for (let y in yearMap)
                for (let m in yearMap[y])
                    for (let d in yearMap[y][m])
                        if (yearMap[y][m][d] > 0)
                            console.log(`${d}/${m}/${y}`,yearMap[y][m][d],'VESTS')
    })
})