import axios from 'axios'

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
request.interceptors.request.use(
  config => {
    // 可以在这里添加token等认证信息
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

// 响应拦截器
request.interceptors.response.use(
  response => {
    const res = response.data
    if (res.code === 200) {
      return res
    } else {
      console.error('请求失败:', res.message)
      // 创建一个包含响应数据的错误对象
      const error = new Error(res.message || '请求失败')
      error.code = res.code
      error.data = res.data
      return Promise.reject(error)
    }
  },
  error => {
    // 处理 HTTP 错误响应（如 409, 500 等）
    if (error.response) {
      const res = error.response.data
      console.error('响应错误:', res?.message || error.message)
      // 创建一个包含响应数据的错误对象
      const customError = new Error(res?.message || error.message)
      customError.code = error.response.status
      customError.data = res
      return Promise.reject(customError)
    }
    console.error('响应错误:', error.message)
    return Promise.reject(error)
  }
)

export default request

