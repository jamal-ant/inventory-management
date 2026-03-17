<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>

      <div v-if="submittedOrder" class="success-banner">
        {{ t('restocking.orderSubmitted', { orderNumber: submittedOrder.order_number }) }}
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.budget') }}</h3>
        </div>
        <div class="budget-control">
          <div class="budget-display">{{ currencySymbol }}{{ budget.toLocaleString() }}</div>
          <input
            type="range"
            min="0"
            max="300000"
            step="5000"
            v-model.number="budget"
            class="budget-slider"
          />
          <div class="budget-labels">
            <span>{{ currencySymbol }}0</span>
            <span>{{ currencySymbol }}300,000</span>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.recommendations') }} ({{ recommendations.length }})</h3>
        </div>

        <div v-if="recommendations.length === 0" class="empty-state">
          {{ t('restocking.noRecommendations') }}
        </div>

        <div v-else>
          <div class="table-container">
            <table>
              <thead>
                <tr>
                  <th>{{ t('restocking.table.sku') }}</th>
                  <th>{{ t('restocking.table.item') }}</th>
                  <th>{{ t('restocking.table.trend') }}</th>
                  <th>{{ t('restocking.table.quantity') }}</th>
                  <th>{{ t('restocking.table.unitCost') }}</th>
                  <th>{{ t('restocking.table.lineTotal') }}</th>
                  <th>{{ t('restocking.table.leadTime') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="rec in recommendations" :key="rec.item_sku">
                  <td><strong>{{ rec.item_sku }}</strong></td>
                  <td>{{ rec.item_name }}</td>
                  <td>
                    <span :class="['badge', rec.trend]">{{ t(`trends.${rec.trend}`) }}</span>
                  </td>
                  <td>{{ rec.recommended_quantity }}</td>
                  <td>{{ currencySymbol }}{{ rec.unit_cost.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}</td>
                  <td>{{ currencySymbol }}{{ rec.line_total.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}</td>
                  <td>{{ rec.lead_time_days }} {{ t('restocking.days') }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="order-summary">
            <div class="order-summary-left">
              <span class="summary-item-count">{{ recommendations.length }} {{ t('restocking.itemCount') }}</span>
              <span class="summary-lead-time">{{ t('restocking.orderLeadTime') }}: {{ orderLeadTime }} {{ t('restocking.days') }}</span>
            </div>
            <div class="order-summary-right">
              <span class="summary-total">{{ t('restocking.orderTotal') }}: {{ currencySymbol }}{{ orderTotal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}</span>
              <button
                class="place-order-btn"
                :disabled="recommendations.length === 0 || submitting"
                @click="placeOrder"
              >
                {{ submitting ? t('restocking.submitting') : t('restocking.placeOrder') }}
              </button>
            </div>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'

export default {
  name: 'Restocking',
  setup() {
    const { t, currentCurrency } = useI18n()
    const currencySymbol = computed(() => currentCurrency.value === 'JPY' ? '¥' : '$')

    const budget = ref(50000)
    const recommendations = ref([])
    const loading = ref(true)
    const error = ref(null)
    const submitting = ref(false)
    const submittedOrder = ref(null)

    const orderTotal = computed(() =>
      recommendations.value.reduce((sum, r) => sum + r.line_total, 0)
    )

    const orderLeadTime = computed(() =>
      recommendations.value.length === 0 ? 0 : Math.max(...recommendations.value.map(r => r.lead_time_days))
    )

    let debounceTimer = null

    const fetchRecommendations = async () => {
      try {
        error.value = null
        recommendations.value = await api.getRestockingRecommendations(budget.value)
      } catch (err) {
        error.value = 'Failed to load recommendations: ' + err.message
      } finally {
        loading.value = false
      }
    }

    watch(budget, () => {
      clearTimeout(debounceTimer)
      debounceTimer = setTimeout(fetchRecommendations, 250)
    })

    const placeOrder = async () => {
      if (recommendations.value.length === 0 || submitting.value) return
      try {
        submitting.value = true
        error.value = null
        const items = recommendations.value.map(r => ({
          item_sku: r.item_sku,
          item_name: r.item_name,
          quantity: r.recommended_quantity,
          unit_cost: r.unit_cost,
          line_total: r.line_total
        }))
        const order = await api.createRestockingOrder(items)
        submittedOrder.value = order
        recommendations.value = []
      } catch (err) {
        error.value = 'Failed to submit order: ' + err.message
      } finally {
        submitting.value = false
      }
    }

    onMounted(fetchRecommendations)

    return {
      t,
      currencySymbol,
      budget,
      recommendations,
      loading,
      error,
      submitting,
      submittedOrder,
      orderTotal,
      orderLeadTime,
      placeOrder
    }
  }
}
</script>

<style scoped>
.budget-control {
  padding: 1rem 0 0.5rem;
}

.budget-display {
  font-size: 1.875rem;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 1rem;
}

.budget-slider {
  width: 100%;
  accent-color: #0f172a;
  height: 6px;
  cursor: pointer;
  display: block;
}

.budget-labels {
  display: flex;
  justify-content: space-between;
  margin-top: 0.5rem;
  font-size: 0.813rem;
  color: #64748b;
}

.empty-state {
  text-align: center;
  padding: 2rem;
  color: #64748b;
}

.order-summary {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 1rem;
  border-top: 1px solid #e2e8f0;
  margin-top: 1rem;
}

.order-summary-left {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.summary-item-count {
  font-size: 0.875rem;
  font-weight: 600;
  color: #0f172a;
}

.summary-lead-time {
  font-size: 0.875rem;
  color: #64748b;
}

.order-summary-right {
  display: flex;
  align-items: center;
  gap: 1.5rem;
}

.summary-total {
  font-size: 1rem;
  font-weight: 700;
  color: #0f172a;
}

.place-order-btn {
  background: #0f172a;
  color: white;
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 6px;
  font-weight: 600;
  font-size: 0.875rem;
  cursor: pointer;
  transition: background 0.2s;
}

.place-order-btn:hover:not(:disabled) {
  background: #1e293b;
}

.place-order-btn:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
}

.success-banner {
  background: #d1fae5;
  border: 1px solid #10b981;
  color: #065f46;
  padding: 1rem;
  border-radius: 8px;
  margin-bottom: 1.25rem;
  font-weight: 500;
}
</style>
