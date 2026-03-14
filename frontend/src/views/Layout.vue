<template>
  <el-container class="layout-container" :class="{ 'is-collapsed': isCollapsed }">
    <!-- 侧边栏 -->
    <el-aside :width="asideWidth" class="sidebar">
      <div class="sidebar-header">
        <el-icon :size="28" color="#409EFF"><DataAnalysis /></el-icon>
        <span class="sidebar-title" v-show="!isCollapsed">DaydayUp</span>
        <div class="sidebar-spacer" />
        <el-button
          class="collapse-btn"
          text
          circle
          size="small"
          :title="isCollapsed ? '展开侧边栏' : '收起侧边栏'"
          @click="toggleCollapse"
        >
          <el-icon>
            <Expand v-if="isCollapsed" />
            <Fold v-else />
          </el-icon>
        </el-button>
      </div>
      
      <el-menu
        :default-active="activeMenu"
        class="sidebar-menu"
        :router="true"
        :collapse="isCollapsed"
        :collapse-transition="true"
      >
        <el-menu-item index="/">
          <el-icon><HomeFilled /></el-icon>
          <span>首页</span>
        </el-menu-item>
        
        <el-sub-menu index="data-group">
          <template #title>
            <el-icon><Connection /></el-icon>
            <span>数据管理</span>
          </template>
          <el-menu-item index="/sync">
            <el-icon><Refresh /></el-icon>
            <span>数据同步</span>
          </el-menu-item>
          <el-menu-item index="/metadata">
            <el-icon><Grid /></el-icon>
            <span>元数据</span>
          </el-menu-item>
        </el-sub-menu>
        
        <el-sub-menu index="review-group">
          <template #title>
            <el-icon><TrendCharts /></el-icon>
            <span>每日复盘</span>
          </template>
          <el-menu-item index="/review">
            <el-icon><List /></el-icon>
            <span>复盘任务</span>
          </el-menu-item>
          <el-menu-item index="/review/create">
            <el-icon><Plus /></el-icon>
            <span>创建复盘</span>
          </el-menu-item>
        </el-sub-menu>

        <el-menu-item index="/cycle">
          <el-icon><Calendar /></el-icon>
          <span>周期管理</span>
        </el-menu-item>
        
        <el-sub-menu index="delivery-group">
          <template #title>
            <el-icon><Document /></el-icon>
            <span>交割单复盘</span>
          </template>
          <el-menu-item index="/delivery/upload">
            <el-icon><Upload /></el-icon>
            <span>上传交割单</span>
          </el-menu-item>
          <el-menu-item index="/delivery/list">
            <el-icon><Tickets /></el-icon>
            <span>交割单列表</span>
          </el-menu-item>
        </el-sub-menu>
        
        <el-sub-menu index="admin-group">
          <template #title>
            <el-icon><Setting /></el-icon>
            <span>因子配置</span>
          </template>
          <el-menu-item index="/admin/factors">
            <el-icon><Operation /></el-icon>
            <span>因子管理</span>
          </el-menu-item>
          <el-menu-item index="/admin/expressions">
            <el-icon><Edit /></el-icon>
            <span>表达式配置</span>
          </el-menu-item>
        </el-sub-menu>
      </el-menu>
    </el-aside>
    
    <!-- 主内容区 -->
    <el-container>
      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const activeMenu = computed(() => {
  return route.path
})

const STORAGE_KEY = 'daydayup.sidebar.collapsed'
const isCollapsed = ref(false)

try {
  isCollapsed.value = localStorage.getItem(STORAGE_KEY) === '1'
} catch (e) {
  // ignore (e.g. SSR / private mode)
}

watch(isCollapsed, (val) => {
  try {
    localStorage.setItem(STORAGE_KEY, val ? '1' : '0')
  } catch (e) {
    // ignore
  }
})

const asideWidth = computed(() => (isCollapsed.value ? '64px' : '240px'))
const toggleCollapse = () => {
  isCollapsed.value = !isCollapsed.value
}
</script>

<style scoped>
.layout-container {
  min-height: 100vh;
}

.sidebar {
  background: #fff;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.08);
  height: 100vh;
  position: fixed;
  left: 0;
  top: 0;
  z-index: 100;
  transition: width 0.2s ease;
}

.sidebar-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 20px 16px;
  border-bottom: 1px solid #ebeef5;
  height: 64px;
  box-sizing: border-box;
}

.sidebar-title {
  font-size: 20px;
  font-weight: 600;
  color: #303133;
  white-space: nowrap;
}

.sidebar-spacer {
  flex: 1;
}

.collapse-btn {
  color: #606266;
}

.sidebar-menu {
  border-right: none;
  padding: 10px 0;
}

.sidebar-menu .el-menu-item,
.sidebar-menu .el-sub-menu__title {
  height: 48px;
  line-height: 48px;
}

.main-content {
  margin-left: 240px;
  background: #f5f7fa;
  min-height: 100vh;
  padding: 20px;
  transition: margin-left 0.2s ease;
}

.layout-container.is-collapsed .main-content {
  margin-left: 64px;
}

/* 收起后让 menu 宽度贴合 aside */
.layout-container.is-collapsed :deep(.el-menu--collapse) {
  width: 64px;
}
</style>
