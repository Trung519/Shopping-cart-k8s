import { useMemo, useState, type FormEvent } from 'react'
import { Pencil, PlusCircle, ShieldCheck, Trash2, Users } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Input } from '@/components/ui/Input'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { useAppAuth } from '@/contexts/AuthContext'
import { useCreateUser, useDeleteUser, useUpdateUser, useUsers } from '@/hooks/useUsers'
import type { ManagedUser, ManagedUserFormInput } from '@/types'

const DEFAULT_FORM: ManagedUserFormInput = {
  username: '',
  password: '',
  name: '',
  email: '',
  countryId: 'VN',
  roles: ['buyer'],
}

const COUNTRY_OPTIONS = [
  ['VN', 'Việt Nam'],
  ['SG', 'Singapore'],
  ['TH', 'Thái Lan'],
  ['MY', 'Malaysia'],
  ['ID', 'Indonesia'],
  ['PH', 'Philippines'],
  ['JP', 'Nhật Bản'],
  ['KR', 'Hàn Quốc'],
  ['US', 'Hoa Kỳ'],
] as const

const countryLabel = (countryId: string) =>
  COUNTRY_OPTIONS.find(([id]) => id === countryId)?.[1] ?? countryId

const ROLE_OPTIONS = [
  ['buyer', 'Người mua'],
  ['seller-owner', 'Chủ shop'],
  ['seller-manager', 'Quản lý shop'],
  ['seller-staff', 'Nhân viên shop'],
  ['support-agent', 'Hỗ trợ khách hàng'],
  ['seller-reviewer', 'Duyệt người bán'],
  ['catalog-moderator', 'Kiểm duyệt sản phẩm'],
  ['order-operator', 'Vận hành đơn'],
  ['finance-operator', 'Vận hành tài chính'],
  ['user-admin', 'Quản trị người dùng'],
  ['platform-admin', 'Quản trị nền tảng'],
] as const

export default function AdminUsersPage() {
  const auth = useAppAuth()
  const { data: users, isLoading, error } = useUsers()
  const createUser = useCreateUser()
  const updateUser = useUpdateUser()
  const deleteUser = useDeleteUser()
  const [editingUser, setEditingUser] = useState<ManagedUser | null>(null)
  const [form, setForm] = useState<ManagedUserFormInput>(DEFAULT_FORM)
  const [submitError, setSubmitError] = useState<string | null>(null)

  const isEditing = Boolean(editingUser)

  const sortedUsers = useMemo(() => users ?? [], [users])

  const startCreate = () => {
    setEditingUser(null)
    setForm(DEFAULT_FORM)
    setSubmitError(null)
  }

  const startEdit = (user: ManagedUser) => {
    setEditingUser(user)
    setForm({
      username: user.username,
      password: '',
      name: user.name,
      email: user.email,
      countryId: user.countryId || 'VN',
      roles: user.roles,
    })
    setSubmitError(null)
  }

  const setField = <K extends keyof ManagedUserFormInput>(field: K, value: ManagedUserFormInput[K]) => {
    setForm((current) => ({ ...current, [field]: value }))
  }

  const toggleRole = (role: string) => {
    setForm((current) => ({
      ...current,
      roles: current.roles.includes(role)
        ? current.roles.filter((item) => item !== role)
        : [...current.roles, role],
    }))
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setSubmitError(null)

    const nextForm = form

    if (nextForm.roles.length === 0) {
      setSubmitError('Hãy chọn ít nhất một vai trò')
      return
    }

    if (!isEditing && nextForm.password.trim() === '') {
      setSubmitError('Tài khoản mới cần có mật khẩu tạm thời')
      return
    }

    try {
      if (isEditing && editingUser) {
        await updateUser.mutateAsync({ id: editingUser.id, input: nextForm })
      } else {
        await createUser.mutateAsync(nextForm)
      }
      startCreate()
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Không thể lưu người dùng')
    }
  }

  const handleDelete = async (user: ManagedUser) => {
    if (user.id === auth.user?.id) {
      setSubmitError('Bạn không thể xóa chính tài khoản đang đăng nhập')
      return
    }

    if (!window.confirm(`Xóa người dùng "${user.username}"?`)) {
      return
    }

    try {
      await deleteUser.mutateAsync(user.id)
      if (editingUser?.id === user.id) {
        startCreate()
      }
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Không thể xóa người dùng')
    }
  }

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (error) {
    return <p className="text-red-600">Không thể tải người dùng: {error.message}</p>
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-ink">Quản lý người dùng</h1>
          <p className="text-sm text-gray-500">Cấp quyền theo vai trò và quản lý quyền truy cập nền tảng.</p>
        </div>
        <Button onClick={startCreate}>
          <PlusCircle className="mr-2 h-4 w-4" />
          Thêm người dùng
        </Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users className="h-5 w-5" />
              Danh sách người dùng
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {sortedUsers.length === 0 && (
              <p className="text-sm text-gray-500">Chưa có người dùng.</p>
            )}

            {sortedUsers.map((user) => (
              <div
                key={user.id}
                className="flex flex-col gap-3 rounded-lg border border-gray-200 p-4 md:flex-row md:items-center md:justify-between"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <p className="font-semibold text-gray-900">{user.name}</p>
                    {user.id === auth.user?.id && (
                      <span className="rounded-full bg-primary-50 px-2 py-0.5 text-xs font-medium text-primary-700">
                        Bạn
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-600">@{user.username}</p>
                  <p className="text-sm text-gray-500">{user.email}</p>
                  <p className="text-sm text-gray-500">Quốc gia: {countryLabel(user.countryId || 'VN')} ({user.countryId || 'VN'})</p>
                  <div className="flex flex-wrap gap-2 pt-1">
                    {user.roles.map((role) => (
                      <span
                        key={role}
                        className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-700"
                      >
                        {role}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button variant="secondary" size="sm" onClick={() => startEdit(user)}>
                    <Pencil className="mr-2 h-4 w-4" />
                    Sửa
                  </Button>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => handleDelete(user)}
                    disabled={deleteUser.isPending && user.id === auth.user?.id}
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    Xóa
                  </Button>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{isEditing ? 'Cập nhật người dùng' : 'Tạo người dùng'}</CardTitle>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={handleSubmit}>
              <label className="block space-y-2 text-sm font-medium text-gray-700">
                <span>Tên đăng nhập</span>
                <Input
                  value={form.username}
                  onChange={(event) => setField('username', event.target.value)}
                  required
                />
              </label>
              <label className="block space-y-2 text-sm font-medium text-gray-700">
                <span>Mật khẩu {isEditing && <span className="text-gray-400">(để trống nếu không đổi)</span>}</span>
                <Input
                  type="password"
                  value={form.password}
                  onChange={(event) => setField('password', event.target.value)}
                  placeholder={isEditing ? 'Giữ mật khẩu hiện tại' : 'Mật khẩu tạm thời'}
                />
              </label>
              <label className="block space-y-2 text-sm font-medium text-gray-700">
                <span>Họ và tên</span>
                <Input
                  value={form.name}
                  onChange={(event) => setField('name', event.target.value)}
                  required
                />
              </label>
              <label className="block space-y-2 text-sm font-medium text-gray-700">
                <span>Email</span>
                <Input
                  type="email"
                  value={form.email}
                  onChange={(event) => setField('email', event.target.value)}
                  required
                />
              </label>
              <label className="block space-y-2 text-sm font-medium text-gray-700">
                <span>Quốc gia</span>
                <select
                  value={form.countryId}
                  onChange={(event) => setField('countryId', event.target.value)}
                  className="h-10 w-full rounded-md border border-gray-300 bg-white px-3 text-sm text-gray-900 shadow-sm outline-none transition focus:border-primary-500 focus:ring-2 focus:ring-primary-200"
                  required
                >
                  {COUNTRY_OPTIONS.map(([id, label]) => (
                    <option key={id} value={id}>{label} ({id})</option>
                  ))}
                </select>
              </label>
              <fieldset className="space-y-3">
                <legend className="flex items-center gap-2 text-sm font-medium text-gray-700">
                  <ShieldCheck className="h-4 w-4" /> Vai trò
                </legend>
                <div className="grid gap-2 sm:grid-cols-2">
                  {ROLE_OPTIONS.map(([role, label]) => (
                    <label key={role} className="flex cursor-pointer items-start gap-2 rounded-md border border-gray-200 p-2.5 text-sm hover:border-primary-300">
                      <input
                        type="checkbox"
                        checked={form.roles.includes(role)}
                        onChange={() => toggleRole(role)}
                        className="mt-0.5 accent-primary-600"
                      />
                      <span><span className="block font-medium text-gray-800">{label}</span><span className="text-xs text-gray-500">{role}</span></span>
                    </label>
                  ))}
                </div>
              </fieldset>

              {submitError && <p className="text-sm text-red-600">{submitError}</p>}

              <div className="flex gap-2">
                <Button
                  type="submit"
                  className="flex-1"
                  loading={createUser.isPending || updateUser.isPending}
                >
                  {isEditing ? 'Lưu thay đổi' : 'Tạo người dùng'}
                </Button>
                {isEditing && (
                  <Button type="button" variant="outline" onClick={startCreate}>
                    Hủy
                  </Button>
                )}
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
