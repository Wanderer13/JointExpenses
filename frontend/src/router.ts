import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from './stores/auth'
import LoginView from './views/LoginView.vue'
import GroupsView from './views/GroupsView.vue'
import GroupDetailView from './views/GroupDetailView.vue'
import JoinView from './views/JoinView.vue'
import MyBalancesView from './views/MyBalancesView.vue'
import NotificationsView from './views/NotificationsView.vue'
import AdminView from './views/AdminView.vue'
import UserProfileView from './views/UserProfileView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: LoginView, meta: { guest: true } },
    { path: '/', name: 'groups', component: GroupsView },
    { path: '/groups/:id', name: 'group', component: GroupDetailView, props: true },
    { path: '/users/:id', name: 'user', component: UserProfileView, props: true },
    { path: '/join/:token', name: 'join', component: JoinView, props: true },
    { path: '/balances', name: 'balances', component: MyBalancesView },
    { path: '/notifications', name: 'notifications', component: NotificationsView },
    { path: '/admin', name: 'admin', component: AdminView, meta: { admin: true } },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.ready) await auth.bootstrap()
  if (to.meta.guest) {
    if (auth.isAuthenticated) return { name: 'groups' }
    return true
  }
  if (!auth.isAuthenticated) return { name: 'login', query: { redirect: to.fullPath } }
  if (to.meta.admin && !auth.isAdmin) return { name: 'groups' }
  return true
})

export default router
