import {check, sleep} from 'k6'
import exec from 'k6/execution'
import {fixture, login, random, recordBusiness, request, responseData, runId} from '../lib/context.js'

export default function sellerApplication() {
  const index = exec.scenario.iterationInTest
  const user = fixture.users.sellerApplication[index]
  if (!user) return recordBusiness('seller_application', false, Date.now())
  if (fixture.config.applicationSpreadSeconds > 0) sleep(random() * fixture.config.applicationSpreadSeconds)
  if (!login(user)) return recordBusiness('seller_application', false, Date.now())
  const started = Date.now()
  const name = `${runId}-pending-shop-${index}`
  const applied = request('seller_application', 'POST', '/api/v2/sellers/applications', {name, description: 'Performance seller application'}, {}, [201], '/api/v2/sellers/applications')
  const application = responseData(applied)
  const mine = request('seller_application', 'GET', '/api/v2/sellers/me', null, {}, [200], '/api/v2/sellers/me')
  const current = responseData(mine)
  const ok = check(applied, {'seller application is submitted once': () => applied.status === 201 && application?.ownerUserId === user.id && application?.status === 'PENDING'}) &&
    check(mine, {'seller application state is persisted': () => mine.status === 200 && current?.id === application?.id && current?.ownerUserId === user.id && current?.name === name && current?.status === 'PENDING'})
  recordBusiness('seller_application', ok, started)
}
