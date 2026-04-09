'use client'

import { useState, useEffect, useRef } from 'react'
import { supabase } from '../lib/supabase'
import { Search, Package, Camera, Send, Trash2, CheckCircle2, Clock, Settings, Menu, X, Pencil, Sun, Moon, Calendar, Check, FileText, FilePlus, FileUp, ChevronDown, ChevronRight, Copy } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

export default function MobileApp() {
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [activeTab, setActiveTab] = useState('pedidos') // pedidos | ingreso | configuracion
  const [defaultPhone, setDefaultPhone] = useState('')
  const [geminiApiKey, setGeminiApiKey] = useState('') // No longer used
  const [supaUrl, setSupaUrl] = useState('')
  const [supaKey, setSupaKey] = useState('')
  const [showSidebar, setShowSidebar] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [showAddForm, setShowAddForm] = useState(false)
  const [showEnviados, setShowEnviados] = useState(false)
  const [showBorradores, setShowBorradores] = useState(false)
  const [showEnviados2, setShowEnviados2] = useState(false)
  const todayStr = () => {
    const d = new Date();
    return `${d.getDate()}/${d.getMonth()+1}/${d.getFullYear().toString().slice(-2)}`;
  }
  const [newOrder, setNewOrder] = useState({ proveedor: '', fecha: todayStr(), itemsText: '' })
  const [editingOrder, setEditingOrder] = useState(null)
  const [showEditForm, setShowEditForm] = useState(false)
  const [confirmDeleteId, setConfirmDeleteId] = useState(null)
  const [darkMode, setDarkMode] = useState(false)
  const [reviewOrders, setReviewOrders] = useState(null)
  const [reviewMetadata, setReviewMetadata] = useState(null) // { tipo, proveedor, numero, fecha, monto, is_remito, remito_vinculado }
  const [showReviewModal, setShowReviewModal] = useState(false)
  const [showPasteModal, setShowPasteModal] = useState(false)
  const [pasteType, setPasteType] = useState('create') // 'create' | 'arrival'
  const [pasteData, setPasteData] = useState({ proveedor: '', fecha: '', rawText: '' })
  const [expandedOrderId, setExpandedOrderId] = useState(null)
  const [scanStatus, setScanStatus] = useState('Iniciando...')
  const [scanPreview, setScanPreview] = useState(null)
  const [showStatusPicker, setShowStatusPicker] = useState(null) // order.id o null
  const fileInputRef = useRef(null) // For images/camera
  const pdfInputRef = useRef(null) // For PDFs
  const processedTasks = useRef(new Set())
  const scanTimeoutRef = useRef(null)

  const isCodeMatch = (codeStr, searchStr) => {
    if (!searchStr || !searchStr.trim()) return false;
    const terms = searchStr.toLowerCase().split(/\s+/).filter(t => t.length > 0);
    const codeLow = String(codeStr || '').toLowerCase();
    const cleanCode = codeLow.replace(/[^a-z0-9]/g, '');
    
    return terms.some(term => {
      const cleanTerm = term.replace(/[^a-z0-9]/g, '');
      return codeLow.includes(term) || (cleanTerm.length > 0 && cleanCode.includes(cleanTerm));
    });
  }

  const formatCode = (code) => {
    if (!code) return ''
    return code.toString().toUpperCase()
  }

  const parseItemsText = (text) => {
    if (!text) return []
    return text.split('\n').filter(line => line.trim()).map(line => {
      // Limpiar corchetes de estado si existen (compatibilidad)
      let cleanLine = line.replace(/\[[vV xX]?\]/, '').replace('[ ]', '').trim()

      const isLlegado = line.toLowerCase().includes('[v]')
      
      // Capturar: CODIGO CANTIDAD NOTA
      const numMatch = cleanLine.match(/^(.+?)\s+([\d.,]+)\s*(.*)$/)
      
      let codigo, cantidad, nota
      if (numMatch) {
        codigo = numMatch[1].trim()
        cantidad = numMatch[2].replace(',', '.')
        nota = numMatch[3].trim() || null
      } else {
        codigo = cleanLine
        cantidad = '1'
        nota = null
      }

      return { codigo: (codigo || '').toString().toUpperCase(), cantidad, nota, llegado: isLlegado }
    })
  }

  const itemsToText = (items) => {
    if (!items) return ''
    return items.map(i => {
      const nota = i.nota ? ` ${i.nota}` : ''
      return `${i.codigo} ${i.cantidad_pedida || i.cantidad || ''}${nota}`
    }).join('\n')
  }

  useEffect(() => {
    const savedPhone = localStorage.getItem('whatsapp_default')
    if (savedPhone) setDefaultPhone(savedPhone)
    const savedKey = localStorage.getItem('gemini_api_key')
    if (savedKey) setGeminiApiKey(savedKey)
    const savedSupaUrl = localStorage.getItem('supabase_url')
    if (savedSupaUrl) setSupaUrl(savedSupaUrl)
    const savedSupaKey = localStorage.getItem('supabase_key')
    if (savedSupaKey) setSupaKey(savedSupaKey)

    const savedTheme = localStorage.getItem('theme')
    const isDark = savedTheme === 'dark'
    setDarkMode(isDark)
    if (isDark) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }

    if (!supabase) return

    fetchOrders()
    const subscription = supabase
      .channel('schema-db-changes')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'pedidos' }, fetchOrders)
      .subscribe()

    return () => {
      supabase.removeChannel(subscription)
    }
  }, [])

  async function fetchOrders() {
    if (!supabase) {
      console.warn('Supabase client not initialized')
      setLoading(false)
      return
    }
    const { data, error } = await supabase
      .from('pedidos')
      .select('*, items(*)')
      .order('id', { ascending: false })

    if (error) {
      console.error('Error fetching orders:', error)
    } else {
      // Deduplicar items por id para evitar duplicados del realtime o de la DB
      const deduped = (data || []).map(o => ({
        ...o,
        items: o.items
          ? [...new Map(o.items.map(i => [i.id, i])).values()]
          : []
      }))
      setOrders(deduped)
    }
    setLoading(false)
  }

  const displayDate = (dateStr) => {
    if (!dateStr) return '-'
    if (dateStr.includes('-')) {
      const [y, m, d] = dateStr.split('-')
      return `${parseInt(d, 10)}/${parseInt(m, 10)}/${y.slice(-2)}`
    }
    return dateStr
  }

  const filteredOrders = orders.filter(o => {
    if (!search || !search.trim()) return true;
    
    // Split search into individual terms for multi-word search (e.g. "Albens 1234")
    const terms = search.toLowerCase().split(/\s+/).filter(t => t.length > 0);
    
    // Every term must match *somewhere* in the order (provider, date, or any item)
    return terms.every(term => {
      const provMatch = (o.proveedor || '').toLowerCase().includes(term);
      const dateMatch = (o.fecha || '').includes(term) || displayDate(o.fecha).includes(term);
      // Items match if ANY item code matches this specific term
      const itemsMatch = (o.items || []).some(item => isCodeMatch(item.codigo, term));
      
      return provMatch || dateMatch || itemsMatch;
    });
  });
  const activeOrders = filteredOrders.filter(o => o.estado?.toLowerCase() !== 'enviado' && o.estado?.toLowerCase() !== 'borrador' && o.estado?.toLowerCase() !== 'enviados 2')
  const borradorOrders = filteredOrders.filter(o => o.estado?.toLowerCase() === 'borrador')
  const enviadosOrders = filteredOrders.filter(o => o.estado?.toLowerCase() === 'enviado')
  const enviados2Orders = filteredOrders.filter(o => o.estado?.toLowerCase() === 'enviados 2')

  const savePhone = (val) => {
    setDefaultPhone(val)
    localStorage.setItem('whatsapp_default', val)
  }

  const saveApiKey = (val) => {
    setGeminiApiKey(val)
    localStorage.setItem('gemini_api_key', val)
  }

  const saveSupaUrl = (val) => {
    setSupaUrl(val)
    localStorage.setItem('supabase_url', val)
    // Reload to use new client if needed, or we could re-init
  }

  const saveSupaKey = (val) => {
    setSupaKey(val)
    localStorage.setItem('supabase_key', val)
  }

  const toggleTheme = () => {
    const newMode = !darkMode
    setDarkMode(newMode)
    if (newMode) {
      document.documentElement.classList.add('dark')
      localStorage.setItem('theme', 'dark')
    } else {
      document.documentElement.classList.remove('dark')
      localStorage.setItem('theme', 'light')
    }
  }
  const handleSmartEnter = (e, field) => {
    if (e.key === 'Enter') {
      const textarea = e.target;
      const start = textarea.selectionStart;
      const text = textarea.value;
      const before = text.substring(0, start);
      const lines = before.split('\n');
      const currentLine = lines[lines.length - 1];
      
      if (currentLine.trim()) {
        e.preventDefault();
        const after = text.substring(start);
        const newValue = before + '\n' + after;
        
        if (field === 'newOrder') {
          setNewOrder({ ...newOrder, itemsText: newValue });
        } else if (field === 'editingOrder') {
          setEditingOrder({ ...editingOrder, itemsText: newValue });
        }
        
        setTimeout(() => {
          textarea.selectionStart = textarea.selectionEnd = start + 1;
          textarea.focus();
        }, 0);
      }
    }
  };

  const handleCheckAll = (field) => {
    if (field === 'editingOrder' && editingOrder) {
      const newText = editingOrder.itemsText.replace(/\[ \]/g, '[V]');
      setEditingOrder({ ...editingOrder, itemsText: newText });
    } else if (field === 'newOrder' && newOrder) {
      const newText = newOrder.itemsText.replace(/\[ \]/g, '[V]');
      setNewOrder({ ...newOrder, itemsText: newText });
    }
  };

  const handleUncheckAll = (field) => {
    if (field === 'editingOrder' && editingOrder) {
      const newText = editingOrder.itemsText.replace(/\[V\]/gi, '[ ]').replace(/\[x\]/gi, '[ ]');
      setEditingOrder({ ...editingOrder, itemsText: newText });
    } else if (field === 'newOrder' && newOrder) {
      const newText = newOrder.itemsText.replace(/\[V\]/gi, '[ ]').replace(/\[x\]/gi, '[ ]');
      setNewOrder({ ...newOrder, itemsText: newText });
    }
  };

  const handleScanClick = () => { // For camera/images
    fileInputRef.current?.click()
  }

  const handleImportClick = () => { // For File Upload (PDF/Image)
    pdfInputRef.current?.click()
  }

  const handlePasteTextClick = (type = 'create') => {
    setPasteType(type)
    setPasteData({ rawText: '' })
    setShowPasteModal(true)
  }

  const handlePasteImport = () => {
    const { rawText } = pasteData
    if (!rawText.trim()) return

    const lines = rawText.split('\n')
    let currentFecha = todayStr()
    let currentProveedor = 'Original'
    let allOrders = []
    let currentArticles = []

    const finalizeOrder = () => {
      if (currentArticles.length > 0) {
        allOrders.push({
          proveedor: currentProveedor,
          fecha: currentFecha,
          articulos: [...currentArticles]
        })
        currentArticles = []
      }
    }

    const dateRegex = /(\d{1,2}\/\d{1,2}\/\d{2,4})/
    
    for (let line of lines) {
      const trimmed = line.trim()
      if (!trimmed) continue

      // 1. Detectar Fecha (ej: "11/3/26")
      const dateMatch = trimmed.match(dateRegex)
      if (dateMatch && trimmed.length < 15) { // Evitar fechas dentro de descripción larga
        finalizeOrder()
        currentFecha = dateMatch[1]
        continue
      }

      // 2. Detectar Proveedor (ej: "Pedido Original" o "Pedido DM")
      const pedidoMatch = trimmed.match(/^pedido\s+(.+)$/i)
      if (pedidoMatch) {
        finalizeOrder()
        currentProveedor = pedidoMatch[1].trim()
        continue
      }

      // 3. Detectar Artículos
      const isLlegado = trimmed.includes('[v]') || trimmed.includes('[V]')
      
      // Limpiar prefijos de checkbox para el código
      let cleanLine = trimmed.replace(/\[[vV xX]?\]/, '').trim()
      
      // Formato "COD X CANT" o "COD CANT"
      const xMatch = cleanLine.match(/^(.+?)\s+[xX*]\s+([\d.,]+)$/)
      if (xMatch) {
        currentArticles.push({
          codigo: xMatch[1].trim(),
          cantidad: xMatch[2].replace(',', '.'),
          llegado: isLlegado
        })
      } else {
        const parts = cleanLine.split(/\s+/)
        if (parts.length >= 2) {
          const lastPart = parts[parts.length - 1].replace(',', '.')
          if (!isNaN(parseFloat(lastPart))) {
            currentArticles.push({
              codigo: parts.slice(0, -1).join(' '),
              cantidad: lastPart,
              llegado: isLlegado
            })
          } else {
            // Si no detecta cantidad, asume 1
            currentArticles.push({
              codigo: cleanLine,
              cantidad: '1',
              llegado: isLlegado
            })
          }
        } else if (cleanLine) {
          currentArticles.push({
            codigo: cleanLine,
            cantidad: '1',
            llegado: isLlegado
          })
        }
      }
    }

    finalizeOrder()

    if (allOrders.length === 0) {
      alert('No se encontraron artículos válidos en el texto.')
      return
    }

    if (pasteType === 'arrival' && allOrders.length > 0) {
      const first = allOrders[0]
      setReviewMetadata({
        tipo: 'TEXTO',
        proveedor: first.proveedor,
        numero: '-',
        fecha: first.fecha,
        monto: '-',
        is_remito: true,
        remito_vinculado: '-',
        rawItems: first.articulos
      })
    }

    setReviewOrders(allOrders)
    setShowPasteModal(false)
    setShowReviewModal(true)
  }

  const handleFileSelect = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    if (!supabase) {
      alert("Configura Supabase en los ajustes primero.")
      return
    }
    setScanning(true)
    setScanStatus('Subiendo imagen...')
    
    // Create local preview
    if (file.type.startsWith('image/')) {
      const reader = new FileReader()
      reader.onload = (re) => setScanPreview(re.target.result)
      reader.readAsDataURL(file)
    } else {
      setScanPreview(null)
    }

    try {
      // 1. Upload to Supabase Storage 'scans' bucket
      const fileExt = file.name.split('.').pop()
      const fileName = `${Math.random().toString(36).substring(2)}-${Date.now()}.${fileExt}`
      const filePath = `uploads/${fileName}`

      const { data: uploadData, error: uploadErr } = await supabase.storage
        .from('scans')
        .upload(filePath, file)

      if (uploadErr) {
        throw new Error(`[PASO 1: SUBIDA FOTO] ${uploadErr.message}`)
      }

      // 2. Insert OCR Task
      const { data: taskData, error: taskErr } = await supabase
        .from('ocr_tasks')
        .insert({ image_url: filePath, status: 'pending' })
        .select()
        .single()

      if (taskErr) {
        throw new Error(`[PASO 2: AVISO TABLA] ${taskErr.message}`)
      }
      const taskId = taskData.id
      
      // 3. Realtime Subscription for completion
      setScanStatus('Esperando a la PC...')
      
      const channel = supabase
        .channel(`task-${taskId}`)
        .on('postgres_changes', 
          { event: 'UPDATE', schema: 'public', table: 'ocr_tasks', filter: `id=eq.${taskId}` }, 
          (payload) => {
            const updatedTask = payload.new
            
            if (updatedTask.status === 'processing') {
              setScanStatus('PC Trabajando...')
            } else if (updatedTask.status === 'completed') {
              supabase.removeChannel(channel)
              handleOCRResult(updatedTask.result_json, taskId)
            } else if (updatedTask.status === 'error') {
              supabase.removeChannel(channel)
              setScanning(false)
              alert("Error en el procesado del PC: " + updatedTask.error_msg)
            }
          }
        )
        .subscribe()

      // Fallback polling (cada 5 seg) en caso de que Realtime falle o sea lento
      const pollInterval = setInterval(async () => {
        // Correct check for scanning state using a closure-safe way if possible, 
        // but here we just want to stop if the task is already processed.
        if (processedTasks.current.has(taskId)) {
          clearInterval(pollInterval)
          return
        }

        const { data, error } = await supabase.from('ocr_tasks').select('*').eq('id', taskId).single()
        if (!error && data && data.status !== 'pending') {
          if (data.status === 'processing') setScanStatus('PC Trabajando...')
          if (data.status === 'completed' || data.status === 'error') {
            clearInterval(pollInterval)
            supabase.removeChannel(channel)
            
            if (data.status === 'completed') {
              handleOCRResult(data.result_json, taskId)
            } else {
              setScanning(false)
              alert("Error en el procesado: " + data.error_msg)
            }
          }
        }
      }, 5000)

      // Fallback timeout total (5 min)
      if (scanTimeoutRef.current) clearTimeout(scanTimeoutRef.current)
      scanTimeoutRef.current = setTimeout(() => {
        clearInterval(pollInterval)
        supabase.removeChannel(channel)
        setScanning((prev) => {
          if (prev) {
            alert("Tiempo de espera agotado (5 min).\n\nPOSIBLES CAUSAS:\n1. La PC está lenta (espera unos segundos más y refresca).\n2. La PC está pausada (presiona ENTER en la ventana negra).\n3. Sin internet.")
            return false
          }
          return false
        })
      }, 300000)

    } catch (err) {
      console.error('Scan Error:', err)
      const msg = err.message || JSON.stringify(err)
      alert(`[ERROR v2.7] ${msg}`)
      setScanning(false)
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = ''
      if (pdfInputRef.current) pdfInputRef.current.value = ''
    }
  }

  const handleOCRResult = (data, taskId) => {
    if (!data) return
    // Clear timeout immediately
    if (scanTimeoutRef.current) clearTimeout(scanTimeoutRef.current)
    
    // Deduplication check
    if (taskId && processedTasks.current.has(taskId)) return
    if (taskId) processedTasks.current.add(taskId)

    setScanning(false)
    setScanPreview(null)
    
    if (data.tipo === 'LISTA_PEDIDOS') {
      const ordersToReview = (data.pedidos_data || []).map(ped => ({
        ...ped,
        fecha: ped.fecha || new Date().toLocaleDateString('es-AR')
      }))
      setReviewOrders(ordersToReview)
      setShowReviewModal(true)
      return
    }

    // Lógica para Factura/Remito
    const fData = data.factura_data || data
    let prov = "-", nro = "-", fec = "-", monto = "-", is_remito = false, link_id = "-"
    
    // El motor local devuelve un formato un poco diferente pero compatible
    // Si viene del motor local 'ocr_engine.py', ya viene mapeado en scanner.py
    for (const item of fData.encabezado || []) {
      const k = item.campo.toLowerCase()
      const v = item.valor
      if (k.includes("proveedor")) prov = v
      else if (k.includes("número") || k.includes("nro")) nro = v
      else if (k.includes("fecha")) fec = v
      else if (k.includes("total") && !k.includes("sub")) monto = v
      else if (k.includes("tipo") && k.includes("documento")) is_remito = v.toLowerCase().includes("remito") && !v.toLowerCase().includes("factura")
      else if (k.includes("remito vinculado")) link_id = v
    }

    const itemsFormatted = (fData.articulos || []).map(i => ({
      codigo: i.codigo || "-",
      descripcion: i.descripcion || "-",
      cantidad: i.cantidad || "1",
      importe: i.importe || "0.00",
      llegado: true
    }))

    setReviewMetadata({
      tipo: data.tipo || 'FACTURA',
      proveedor: prov,
      numero: nro,
      fecha: fec,
      monto: monto,
      is_remito: is_remito,
      remito_vinculado: link_id,
      rawItems: itemsFormatted
    })

    setReviewOrders([{
      proveedor: prov,
      fecha: fec,
      articulos: itemsFormatted
    }])

    setShowReviewModal(true)
  }

  const formatDateForDB = (dateStr) => {
    if (!dateStr) return todayStr()
    const parts = dateStr.split('/')
    if (parts.length === 3) {
      const d = parts[0].padStart(2, '0')
      const m = parts[1].padStart(2, '0')
      let y = parts[2]
      if (y.length === 2) y = '20' + y
      return `${y}-${m}-${d}`
    }
    return dateStr
  }

  const handleCreateOrder = async () => {
    if (!supabase) {
      alert("Por favor, configura Supabase en los ajustes primero.")
      setActiveTab('configuracion')
      return
    }
    if (!newOrder.proveedor || !newOrder.itemsText.trim()) return

    setLoading(true)
    try {
      const items = parseItemsText(newOrder.itemsText)
      if (items.length === 0) return

      const fecha = formatDateForDB(newOrder.fecha || todayStr())

      // 1. Insertar Pedido
      const { data: pedidoData, error: pedErr } = await supabase
        .from('pedidos')
        .insert({
          fecha,
          proveedor: newOrder.proveedor.toUpperCase(),
          repuesto: newOrder.proveedor.toUpperCase() // Satisfacer restricción NOT NULL
        })
        .select()

      if (pedErr) {
        console.error('PedErr:', pedErr)
        throw new Error(pedErr.message || pedErr.details || JSON.stringify(pedErr))
      }

      if (!pedidoData || pedidoData.length === 0) {
        throw new Error("No se recibió respuesta al crear el pedido. Verifica los permisos (RLS).")
      }

      const pedidoId = pedidoData[0].id

      // 2. Insertar Items
      const itemsToInsert = items.map(item => ({
        pedido_id: pedidoId,
        codigo: item.codigo,
        cantidad_pedida: parseFloat(item.cantidad) || 0,
        cantidad_entregada: 0,
        nota: item.nota || null
      }))

      const { error: itemErr } = await supabase
        .from('items')
        .insert(itemsToInsert)

      if (itemErr) {
        console.error('ItemErr:', itemErr)
        throw new Error(itemErr.message || itemErr.details || JSON.stringify(itemErr))
      }

      setNewOrder({ proveedor: '', fecha: todayStr(), itemsText: '' })
      setShowAddForm(false)
      fetchOrders()
    } catch (err) {
      console.error('Full Error:', err)
      const errorDetail = err.message || (typeof err === 'object' ? JSON.stringify(err, Object.getOwnPropertyNames(err)) : String(err))
      alert("Error creando pedido: " + errorDetail)
    } finally {
      setLoading(false)
    }
  }

  const handleReviewOrderChange = (idx, field, value) => {
    setReviewOrders(prev => {
      const copy = [...prev]
      copy[idx] = { ...copy[idx], [field]: value }
      return copy
    })
  }

  const handleReviewItemChange = (orderIdx, itemIdx, field, value) => {
    setReviewOrders(prev => {
      const copy = [...prev]
      const orderCopy = { ...copy[orderIdx] }
      const itemsCopy = [...orderCopy.articulos]
      itemsCopy[itemIdx] = { ...itemsCopy[itemIdx], [field]: value }
      orderCopy.articulos = itemsCopy
      copy[orderIdx] = orderCopy
      return copy
    })
  }

  const handleConfirmImport = async () => {
    if (!supabase || !reviewOrders) return
    setLoading(true)
    try {
      if (reviewMetadata) {
        // --- CASO FACTURA / REMITO ---
        const { proveedor, numero, fecha, monto, is_remito, remito_vinculado } = reviewMetadata
        const finalNro = numero === "-" ? "S/N-" + Date.now().toString().slice(-6) : numero
        const estado = is_remito ? "Pendiente" : "Completado"
        
        // Solo los artículos marcados como "llegados" en la revisión
        const articlesToSync = reviewOrders[0].articulos.filter(a => a.llegado)
        const allItemsFormatted = reviewOrders[0].articulos.map(i => [
          i.codigo, i.descripcion, i.cantidad, i.importe, i.llegado
        ])

        // 1. Guardar en Historia
        const { error: histErr } = await supabase.from('documentos_historia').insert({
          proveedor: proveedor,
          documento_id: finalNro,
          fecha: fecha,
          monto: monto,
          estado: estado,
          is_remito: is_remito,
          remito_vinculado: remito_vinculado,
          items_json: JSON.stringify(allItemsFormatted),
          totals_json: JSON.stringify({ total: monto, subtotal: "-" })
        })

        if (histErr) throw histErr

        // 2. Sincronizar con Pedidos Pendientes
        if (articlesToSync.length > 0) {
          const { data: pendingOrders, error: pedErr } = await supabase
            .from('pedidos')
            .select('*, items(*)')
            .neq('estado', 'Completado')
            .order('id', { ascending: true })

          if (!pedErr && pendingOrders?.length > 0) {
            for (const article of articlesToSync) {
              let remainingToDeliver = parseFloat(article.cantidad.toString().replace(',', '.')) || 0
              if (remainingToDeliver <= 0) continue

              for (const order of pendingOrders) {
                if (remainingToDeliver <= 0) break
                let updatedOrderItems = false

                for (const item of order.items) {
                  if (remainingToDeliver <= 0) break
                  // Match por código
                  if (article.codigo.toUpperCase().includes(item.codigo.toUpperCase()) || item.codigo.toUpperCase().includes(article.codigo.toUpperCase())) {
                    const needed = item.cantidad_pedida - item.cantidad_entregada
                    if (needed > 0) {
                      const addNow = Math.min(remainingToDeliver, needed)
                      const newDelivered = item.cantidad_entregada + addNow
                      await supabase.from('items').update({ cantidad_entregada: newDelivered }).eq('id', item.id)
                      remainingToDeliver -= addNow
                      updatedOrderItems = true
                    }
                  }
                }

                if (updatedOrderItems) {
                  const { data: refreshedItems } = await supabase.from('items').select('cantidad_pedida, cantidad_entregada').eq('pedido_id', order.id)
                  if (refreshedItems) {
                    const total = refreshedItems.length
                    const comp = refreshedItems.filter(i => i.cantidad_entregada >= i.cantidad_pedida).length
                    const some = refreshedItems.some(i => i.cantidad_entregada > 0)
                    const newState = comp === total ? 'Completado' : (some ? 'Parcial' : 'Pendiente')
                    await supabase.from('pedidos').update({ estado: newState }).eq('id', order.id)
                  }
                }
              }
            }
          }
        }
        alert(`Ingreso confirmado: ${proveedor} #${finalNro}`)
      } else {
        // --- CASO LISTA_PEDIDOS (Creación de Pedidos) ---
        const results = []
        const errors = []

        for (const ped of reviewOrders) {
          const fecha = formatDateForDB(ped.fecha)
          const { data: pedidoData, error: pedErr } = await supabase
            .from('pedidos')
            .insert({ 
              fecha: fecha, 
              proveedor: ped.proveedor.toUpperCase(), 
              repuesto: ped.proveedor.toUpperCase(),
              estado: 'Borrador'
            })
            .select()

          if (pedErr) {
            errors.push(`Error en ${ped.proveedor}: ${pedErr.message}`)
            continue
          }

          if (pedidoData?.[0]) {
            const pedidoId = pedidoData[0].id
            const itemsToInsert = (ped.articulos || []).map(item => {
              const cant = parseFloat(item.cantidad) || 0
              return {
                pedido_id: pedidoId,
                codigo: item.codigo,
                cantidad_pedida: cant,
                cantidad_entregada: item.llegado ? cant : 0
              }
            })
            const { error: itemErr } = await supabase.from('items').insert(itemsToInsert)
            if (itemErr) errors.push(`Error items ${ped.proveedor}: ${itemErr.message}`)
            else results.push(ped.proveedor)
          }
        }

        if (errors.length > 0) alert(`Importación parcial:\nExitosos: ${results.length}\nErrores:\n${errors.join('\n')}`)
        else alert(`Importados ${results.length} pedidos con éxito.`)
      }

      setShowReviewModal(false)
      setReviewOrders(null)
      setReviewMetadata(null)
      fetchOrders()
    } catch (err) {
      console.error('Import Error:', err)
      alert('Error en la importación final: ' + err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleToggleLlegado = (orderIdx, artIdx) => {
    const updated = [...reviewOrders]
    updated[orderIdx].articulos[artIdx].llegado = !updated[orderIdx].articulos[artIdx].llegado
    setReviewOrders(updated)
  }

  const handleDeleteOrder = async (id) => {
    if (!supabase) return

    setLoading(true)
    try {
      const { error } = await supabase
        .from('pedidos')
        .delete()
        .eq('id', id)

      if (error) throw error

      setConfirmDeleteId(null)
      fetchOrders()
    } catch (err) {
      console.error('Error deleting:', err)
      alert('Error eliminando pedido: ' + (err.message || String(err)))
    } finally {
      setLoading(false)
    }
  }

  const handleEditClick = (order) => {
    setEditingOrder({
      ...order,
      fecha: displayDate(order.fecha),
      itemsText: itemsToText(order.items)
    })
    setShowEditForm(true)
  }

  const handleUpdateOrder = async () => {
    if (!supabase || !editingOrder) return
    if (!editingOrder.proveedor || !editingOrder.itemsText.trim()) return

    setLoading(true)
    try {
      const items = parseItemsText(editingOrder.itemsText)
      // Preservar cantidades entregadas si el código coincide
      const oldItems = editingOrder.items || []

      // 1. Actualizar Pedido
      const fechaDB = formatDateForDB(editingOrder.fecha)
      const { error: pedErr } = await supabase
        .from('pedidos')
        .update({
          proveedor: editingOrder.proveedor.toUpperCase(),
          fecha: fechaDB
        })
        .eq('id', editingOrder.id)

      if (pedErr) throw pedErr

      // 2. Sincronizar Items (Enfoque simple: borrar y re-insertar para asegurar integridad)
      // Aunque lo ideal es actualizar, borrar y re-insertar es más robusto para listas variables en mobile
      const { error: delErr } = await supabase
        .from('items')
        .delete()
        .eq('pedido_id', editingOrder.id)

      if (delErr) throw delErr

      const itemsToInsert = items.map(item => {
        const old = oldItems.find(oi => oi.codigo === item.codigo)
        const cantPedida = parseFloat(item.cantidad) || 0
        // Si el usuario puso [v] en el texto, marcamos como entregado al 100%
        // De lo contrario, preservamos lo que ya estaba entregado
        const cantEntregada = item.llegado ? cantPedida : (old ? old.cantidad_entregada : 0)
        
        return {
          pedido_id: editingOrder.id,
          codigo: item.codigo,
          cantidad_pedida: cantPedida,
          cantidad_entregada: cantEntregada,
          nota: item.nota || null
        }
      })

      const { error: itemErr } = await supabase
        .from('items')
        .insert(itemsToInsert)

      if (itemErr) throw itemErr

      setShowEditForm(false)
      setEditingOrder(null)
      fetchOrders()
    } catch (err) {
      console.error('Error updating:', err)
      alert('Error actualizando pedido: ' + (err.message || String(err)))
    } finally {
      setLoading(false)
    }
  }

  const handleChangeEstado = async (orderId, newEstado) => {
    if (!supabase) return
    setShowStatusPicker(null)
    const { error } = await supabase
      .from('pedidos')
      .update({ estado: newEstado })
      .eq('id', orderId)
    if (!error) {
      setOrders(prev => prev.map(o => o.id === orderId ? { ...o, estado: newEstado } : o))
    } else {
      alert('Error cambiando estado: ' + error.message)
    }
  }

  // Agrupa items: primero los sin nota, luego cada grupo de nota separado por \n\n
  const groupItemsForMessage = (items, sep = 'X') => {
    // Dedup por id (por las dudas)
    const uniqueItems = [...new Map(items.map(i => [i.id, i])).values()]
    const sinNota = uniqueItems.filter(i => !i.nota)
    const conNota = {}
    uniqueItems.filter(i => i.nota).forEach(i => {
      if (!conNota[i.nota]) conNota[i.nota] = []
      conNota[i.nota].push(i)
    })
    const sections = []
    if (sinNota.length > 0)
      sections.push(sinNota.map(i => `${formatCode(i.codigo)} ${sep} ${i.cantidad_pedida}`).join('\n'))
    for (const nota of Object.keys(conNota))
      sections.push(conNota[nota].map(i => `${formatCode(i.codigo)} ${sep} ${i.cantidad_pedida} ${nota}`).join('\n'))
    return sections.join('\n\n')
  }

  const handleCopyOrder = (order) => {
    const header = `Pedido ${order.proveedor} (${displayDate(order.fecha)})`
    const textToCopy = `${header}\n${groupItemsForMessage(order.items, 'x')}`
    navigator.clipboard.writeText(textToCopy)
      .then(() => alert('Pedido copiado al portapapeles ✓'))
      .catch(() => alert('No se pudo copiar. Intentá de nuevo.'))
  }

  const shareOnWhatsApp = async (order) => {
    const message = `Pedido ${order.proveedor}\n${groupItemsForMessage(order.items, 'X')}`

    let url = `whatsapp://send?text=${encodeURIComponent(message)}`
    if (defaultPhone) {
      url = `whatsapp://send?phone=${defaultPhone.replace(/\D/g, '')}&text=${encodeURIComponent(message)}`
    }

    if (supabase && order.estado?.toLowerCase() === 'pendiente') {
      const { error } = await supabase
        .from('pedidos')
        .update({ estado: 'Enviado' })
        .eq('id', order.id)
      
      if (!error) {
        setOrders(prev => prev.map(o => o.id === order.id ? { ...o, estado: 'Enviado' } : o))
      }
    }

    window.location.href = url
  }

  const renderOrderCard = (order) => {
    const isExpanded = expandedOrderId === order.id;
    return (
      <motion.div
        layout
        key={order.id}
        className="ios-card bg-white dark:bg-[#1a1a1a] p-4 mb-3 shadow-md transition-all cursor-pointer border border-gray-100 dark:border-white/5"
        onClick={() => setExpandedOrderId(isExpanded ? null : order.id)}
      >
        {/* Card Header */}
        <div className="flex items-start gap-2">
          {/* Left: Chevron + Info */}
          <div className="flex items-center gap-2 flex-1 min-w-0 pt-0.5">
            <div className="text-gray-400 shrink-0">
              {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
            </div>
            <div className="min-w-0">
              <span className="text-[10px] font-bold uppercase tracking-widest text-gray-400 dark:text-gray-500">{displayDate(order.fecha)}</span>
              <h3 className="text-base font-bold leading-tight dark:text-gray-100 capitalize truncate">{order.proveedor}</h3>
            </div>
          </div>

          {/* Right: Action Pill + Badge */}
          <div className="flex flex-col items-end gap-1.5 shrink-0" onClick={(e) => e.stopPropagation()}>
            {/* Action Pill */}
            <AnimatePresence mode="wait">
              {confirmDeleteId === order.id ? (
                <motion.div
                  key="confirm"
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.9 }}
                  className="flex gap-1.5"
                >
                  <button
                    onClick={() => handleDeleteOrder(order.id)}
                    className="px-3 h-8 bg-red-600 text-white rounded-full font-bold text-[11px] transition-all active:scale-95"
                  >
                    Confirmar
                  </button>
                  <button
                    onClick={() => setConfirmDeleteId(null)}
                    className="px-3 h-8 bg-gray-100 dark:bg-white/10 rounded-full text-[11px] font-medium transition-all dark:text-gray-300"
                  >
                    No
                  </button>
                </motion.div>
              ) : (
                <motion.div
                  key="actions"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="flex items-center gap-0.5 bg-gray-100 dark:bg-white/5 rounded-full px-1 py-1"
                >
                  <button
                    onClick={() => shareOnWhatsApp(order)}
                    title="Enviar por WhatsApp"
                    className="w-8 h-8 rounded-full flex items-center justify-center text-blue-500 hover:bg-blue-500/10 transition-colors active:scale-90"
                  >
                    <Send className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => handleCopyOrder(order)}
                    title="Copiar al portapapeles"
                    className="w-8 h-8 rounded-full flex items-center justify-center text-gray-500 dark:text-gray-400 hover:bg-black/5 dark:hover:bg-white/10 transition-colors active:scale-90"
                  >
                    <Copy className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => handleEditClick(order)}
                    title="Editar pedido"
                    className="w-8 h-8 rounded-full flex items-center justify-center text-gray-500 dark:text-gray-400 hover:bg-black/5 dark:hover:bg-white/10 transition-colors active:scale-90"
                  >
                    <Pencil className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => setConfirmDeleteId(order.id)}
                    title="Eliminar pedido"
                    className="w-8 h-8 rounded-full flex items-center justify-center text-red-400 hover:bg-red-500/10 transition-colors active:scale-90"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Status Badge + article count */}
            <div className="flex items-center gap-1.5 relative">
              {!isExpanded && (
                <span className="text-[10px] text-gray-400 italic">{order.items.length} art.</span>
              )}
              <div className="relative">
                <StatusBadge
                  status={order.estado}
                  onClick={(e) => { e.stopPropagation(); setShowStatusPicker(showStatusPicker === order.id ? null : order.id) }}
                />
                {showStatusPicker === order.id && (
                  <StatusPickerDropdown
                    currentStatus={order.estado}
                    onSelect={(s) => handleChangeEstado(order.id, s)}
                    onClose={() => setShowStatusPicker(null)}
                  />
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Expanded: Items List */}
        <AnimatePresence>
          {isExpanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="overflow-hidden"
            >
              {(() => {
                const uniqueItems = [...new Map(order.items.map(i => [i.id, i])).values()]
                // Agrupar por nota (null = sin nota, resto = marca específica)
                const groups = []
                let lastNota = undefined
                for (const item of uniqueItems) {
                  const nota = item.nota || null
                  if (nota !== lastNota) {
                    groups.push({ nota, items: [item] })
                    lastNota = nota
                  } else {
                    groups[groups.length - 1].items.push(item)
                  }
                }
                return (
                  <div className="mt-4 p-4 bg-gray-50 dark:bg-white/5 rounded-2xl">
                    {groups.map((group, gIdx) => (
                      <div key={gIdx}>
                        {gIdx > 0 && <div className="border-t border-gray-200 dark:border-white/10 my-2" />}
                        {group.items.map(item => (
                          <div key={item.id} className="flex justify-between items-center text-sm py-0.5">
                            <div className="flex items-baseline gap-2">
                              <span className={`${item.cantidad_entregada >= item.cantidad_pedida ? "text-gray-400 dark:text-gray-600 line-through" : "dark:text-gray-300"} ${search && isCodeMatch(item.codigo, search) ? "bg-yellow-200 dark:bg-yellow-900/50 text-yellow-900 dark:text-yellow-100 px-1 rounded-md" : ""}`}>
                                {formatCode(item.codigo)}
                              </span>
                              {item.nota && (
                                <span className="text-[9px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded-full bg-orange-100 text-orange-600 dark:bg-orange-500/15 dark:text-orange-400">
                                  {item.nota}
                                </span>
                              )}
                            </div>
                            <span className="font-mono text-xs bg-white dark:bg-black/20 px-2.5 py-1.5 rounded-xl shadow-sm dark:text-gray-400">
                              {item.cantidad_entregada} / {item.cantidad_pedida}
                            </span>
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                )
              })()}
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    );
  }

  return (
    <main className="max-w-md mx-auto min-h-screen pb-24">
      {/* Header */}
      <div className="sticky top-0 z-20 glass-panel px-6 pt-12 pb-4 flex items-center gap-4">
        <button
          onClick={() => setShowSidebar(true)}
          className="p-2.5 -ml-2 text-gray-800 dark:text-gray-100 hover:bg-black/5 dark:hover:bg-white/5 rounded-2xl transition-all active:scale-90"
        >
          <Menu className="w-6 h-6" />
        </button>
        <div className="flex-1">
          <h1 className="text-xl font-extrabold tracking-tight">
            {activeTab === 'pedidos' ? 'Pedidos' :
              activeTab === 'ingreso' ? 'Escanear' : 'Ajustes'}
            <button 
              onClick={() => window.location.reload(true)} 
              className="ml-2 text-[10px] font-medium text-blue-500 bg-blue-500/10 hover:bg-blue-500/20 px-2 py-0.5 rounded-full border border-blue-500/20 shadow-sm active:scale-95 transition-all"
              title="Actualizar Aplicación"
            >
              🔄 Actualizar v2.8 - Borradores
            </button>
          </h1>
        </div>
        <div className="w-8 h-8 bg-blue-500/10 rounded-full flex items-center justify-center">
          <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto px-4 py-6 pb-24 relative z-0">
        <AnimatePresence mode="wait">
          {activeTab === 'pedidos' && (
            <motion.div
              key="pedidos"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              className="space-y-4 pt-4"
            >
              <div className="flex justify-between items-center mb-2 px-1">
                <h2 className="text-sm font-bold text-gray-400 uppercase tracking-widest">Gestión de Pedidos</h2>
                <div className="flex gap-2">
                  <button
                    onClick={() => handlePasteTextClick('create')}
                    className="px-3 py-2 bg-purple-500/10 text-purple-600 dark:bg-purple-500/20 dark:text-purple-400 rounded-xl text-[10px] font-bold transition-all flex items-center gap-2"
                  >
                    <FileText className="w-3.5 h-3.5" /> Pegar Texto
                  </button>
                  <button
                    onClick={() => setShowAddForm(!showAddForm)}
                    className={`px-4 py-2 rounded-xl text-xs font-bold transition-all ${showAddForm ? 'bg-red-500/10 text-red-500' : 'bg-blue-500/10 text-blue-500'}`}
                  >
                    {showAddForm ? 'Cancelar' : '+ Nuevo Pedido'}
                  </button>
                </div>
              </div>

              {/* Expandable Add Order Form */}
              <AnimatePresence>
                {showAddForm && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="overflow-hidden mb-6"
                  >
                    <div className="ios-card p-6 bg-blue-50/50 dark:bg-blue-500/5 border-blue-100 dark:border-blue-500/20">
                      <div className="space-y-4">
                        <div className="flex gap-3">
                          <div className="flex-1">
                            <label className="block text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-1.5">Proveedor</label>
                            <input
                              type="text"
                              placeholder="Nombre del proveedor"
                              className="w-full bg-white dark:bg-gray-800 border border-gray-100 dark:border-gray-800 rounded-2xl px-5 py-3.5 outline-none focus:ring-2 ring-blue-500/20 shadow-sm"
                              value={newOrder.proveedor}
                              onChange={(e) => setNewOrder({ ...newOrder, proveedor: e.target.value })}
                            />
                          </div>
                          <div className="w-32">
                            <label className="block text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-1.5">Fecha</label>
                            <input
                              type="text"
                              placeholder="dd/mm/aaaa"
                              className="w-full bg-white dark:bg-gray-800 border border-gray-100 dark:border-gray-800 rounded-2xl px-3 py-3.5 outline-none focus:ring-2 ring-blue-500/20 shadow-sm text-sm"
                              value={newOrder.fecha}
                              onChange={(e) => setNewOrder({ ...newOrder, fecha: e.target.value })}
                            />
                          </div>
                        </div>

                        <div className="space-y-3">
                          <label className="block text-[10px] font-bold text-gray-400 uppercase tracking-widest">Artículos (Código Cantidad)</label>
                          <textarea
                            placeholder="Ejemplo:&#10;9818914980 10&#10;04/087/039 2"
                            className="w-full h-48 bg-white dark:bg-gray-800 border border-gray-100 dark:border-gray-800 rounded-2xl px-5 py-2 text-sm outline-none shadow-sm notebook-textarea resize-none"
                            value={newOrder.itemsText}
                            onChange={(e) => setNewOrder({ ...newOrder, itemsText: e.target.value })}
                            onKeyDown={(e) => handleSmartEnter(e, 'newOrder')}
                          />
                          <div className="flex justify-between items-center px-1 flex-wrap gap-2 mt-1">
                            <p className="text-[10px] text-gray-400 italic flex-1 min-w-[200px]">Escribe un producto por línea. El espacio separa el código de la cantidad.</p>
                            <div className="flex gap-4">
                              <button
                                onClick={() => handleUncheckAll('newOrder')}
                                className="text-[10px] font-bold text-gray-400 uppercase tracking-tight hover:text-gray-600 transition-colors"
                              >
                                Desmarcar Todos
                              </button>
                              <button
                                onClick={() => handleCheckAll('newOrder')}
                                className="text-[10px] font-bold text-blue-500 uppercase tracking-tight hover:underline"
                              >
                                Tachar Todos
                              </button>
                            </div>
                          </div>
                        </div>

                        <button
                          onClick={handleCreateOrder}
                          disabled={!newOrder.proveedor || !newOrder.itemsText.trim()}
                          className="w-full h-14 bg-blue-600 text-white rounded-2xl font-bold shadow-lg shadow-blue-500/20 disabled:opacity-50 disabled:grayscale transition-all active:scale-95 flex items-center justify-center gap-3 mt-2"
                        >
                          <Package className="w-5 h-5" />
                          Registrar Pedido
                        </button>
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Edit Order Form Modal/Overlay */}
              <AnimatePresence>
                {showEditForm && editingOrder && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-end sm:items-center justify-center p-4"
                  >
                    <motion.div
                      initial={{ y: '100%' }}
                      animate={{ y: 0 }}
                      exit={{ y: '100%' }}
                      className="ios-card w-full max-w-lg bg-white dark:bg-gray-900 p-6 overflow-y-auto max-h-[90vh]"
                    >
                      <div className="flex justify-between items-center mb-6">
                        <h2 className="text-xl font-bold">Editar Pedido</h2>
                        <button onClick={() => setShowEditForm(false)} className="p-2 text-gray-400">
                          <X className="w-6 h-6" />
                        </button>
                      </div>

                      <div className="space-y-4">
                        <div className="flex gap-3">
                          <div className="flex-1">
                            <label className="block text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-1.5">Proveedor</label>
                            <input
                              type="text"
                              className="w-full bg-black/5 dark:bg-white/5 border border-transparent rounded-2xl px-5 py-3.5 outline-none focus:ring-2 ring-blue-500/20"
                              value={editingOrder.proveedor}
                              onChange={(e) => setEditingOrder({ ...editingOrder, proveedor: e.target.value })}
                            />
                          </div>
                          <div className="w-32">
                            <label className="block text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-1.5">Fecha</label>
                            <input
                              type="text"
                              placeholder="dd/mm/aaaa"
                              className="w-full bg-black/5 dark:bg-white/5 border border-transparent rounded-2xl px-3 py-3.5 outline-none focus:ring-2 ring-blue-500/20 text-sm"
                              value={editingOrder.fecha || ''}
                              onChange={(e) => setEditingOrder({ ...editingOrder, fecha: e.target.value })}
                            />
                          </div>
                        </div>

                        <div className="space-y-3">
                          <label className="block text-[10px] font-bold text-gray-400 uppercase tracking-widest">Artículos (Código Cantidad)</label>
                          <textarea
                            placeholder="9818914980 10&#10;04/087/039 2"
                            className="w-full h-48 bg-black/5 dark:bg-white/5 border border-transparent rounded-2xl px-5 py-2 text-sm outline-none notebook-textarea resize-none"
                            value={editingOrder.itemsText}
                            onChange={(e) => setEditingOrder({ ...editingOrder, itemsText: e.target.value })}
                            onKeyDown={(e) => handleSmartEnter(e, 'editingOrder')}
                          />
                          <div className="flex justify-between items-center px-1 flex-wrap gap-2 mt-1">
                            <p className="text-[10px] text-gray-400 italic flex-1 min-w-[200px]">Escribe un producto por línea. El espacio separa el código de la cantidad.</p>
                            <div className="flex gap-4">
                              <button
                                onClick={() => handleUncheckAll('editingOrder')}
                                className="text-[10px] font-bold text-gray-400 uppercase tracking-tight hover:text-gray-600 transition-colors"
                              >
                                Desmarcar Todos
                              </button>
                              <button
                                onClick={() => handleCheckAll('editingOrder')}
                                className="text-[10px] font-bold text-blue-500 uppercase tracking-tight hover:underline"
                              >
                                Tachar Todos
                              </button>
                            </div>
                          </div>
                        </div>

                        <button
                          onClick={handleUpdateOrder}
                          className="w-full h-14 bg-blue-600 text-white rounded-2xl font-bold shadow-lg mt-4 active:scale-95 transition-all"
                        >
                          Guardar Cambios
                        </button>
                      </div>
                    </motion.div>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Search */}
              <div className="relative mt-6">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-[--text-secondary] w-4 h-4" />
                <input
                  type="text"
                  placeholder="Buscar por proveedor, fecha o código..."
                  className="w-full pl-11 pr-4 py-3 bg-black/5 dark:bg-white/5 rounded-2xl outline-none focus:ring-2 ring-[--accent]/20 transition-all border border-transparent"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>

              {/* Orders List */}
              <section className="px-1 py-6 space-y-4">
                {loading ? (
                  <div className="text-center py-20 text-[--text-secondary]">Cargando pedidos...</div>
                ) : filteredOrders.length === 0 ? (
                  <div className="text-center py-20 text-gray-400">
                    {search ? 'No se encontraron repuestos o pedidos con esa búsqueda.' : 'No hay pedidos. ¡Añade uno nuevo!'}
                  </div>
                ) : (
                  <>
                    <AnimatePresence>
                      {activeOrders.map(renderOrderCard)}
                    </AnimatePresence>

                    {borradorOrders.length > 0 && (
                      <div className="pt-6 mt-4 border-t border-gray-100 dark:border-white/5">
                        <button 
                          onClick={() => setShowBorradores(!showBorradores)}
                          className="w-full flex items-center justify-between p-4 bg-orange-50 dark:bg-orange-900/20 rounded-2xl border border-orange-100 dark:border-orange-900/30 active:scale-[0.98] transition-all"
                        >
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-orange-100 dark:bg-orange-900/50 flex items-center justify-center text-orange-600 dark:text-orange-400">
                              <FileText className="w-4 h-4" />
                            </div>
                            <span className="font-bold text-orange-700 dark:text-orange-300">Borradores Texto ({borradorOrders.length})</span>
                          </div>
                          <div className="text-orange-400">
                            {(showBorradores || search.trim().length > 0) ? <ChevronDown className="w-5 h-5" /> : <ChevronRight className="w-5 h-5" />}
                          </div>
                        </button>
                        
                        <AnimatePresence>
                          {(showBorradores || search.trim().length > 0) && (
                            <motion.div
                              initial={{ height: 0, opacity: 0 }}
                              animate={{ height: 'auto', opacity: 1 }}
                              exit={{ height: 0, opacity: 0 }}
                              className="overflow-hidden space-y-3 mt-4"
                            >
                              {borradorOrders.map(renderOrderCard)}
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </div>
                    )}

                    {enviadosOrders.length > 0 && (
                      <div className="pt-6 mt-4 border-t border-gray-100 dark:border-white/5">
                        <button 
                          onClick={() => setShowEnviados(!showEnviados)}
                          className="w-full flex items-center justify-between p-4 bg-purple-50 dark:bg-purple-900/20 rounded-2xl border border-purple-100 dark:border-purple-900/30 active:scale-[0.98] transition-all"
                        >
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-purple-100 dark:bg-purple-900/50 flex items-center justify-center text-purple-600 dark:text-purple-400">
                              <Send className="w-4 h-4" />
                            </div>
                            <span className="font-bold text-purple-700 dark:text-purple-300">Pedidos Enviados ({enviadosOrders.length})</span>
                          </div>
                          <div className="text-purple-400">
                            {(showEnviados || search.trim().length > 0) ? <ChevronDown className="w-5 h-5" /> : <ChevronRight className="w-5 h-5" />}
                          </div>
                        </button>
                        
                        <AnimatePresence>
                          {(showEnviados || search.trim().length > 0) && (
                            <motion.div
                              initial={{ height: 0, opacity: 0 }}
                              animate={{ height: 'auto', opacity: 1 }}
                              exit={{ height: 0, opacity: 0 }}
                              className="overflow-hidden space-y-3 mt-4"
                            >
                              {enviadosOrders.map(renderOrderCard)}
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </div>
                    )}

                    {enviados2Orders.length > 0 && (
                      <div className="pt-6 mt-4 border-t border-gray-100 dark:border-white/5">
                        <button 
                          onClick={() => setShowEnviados2(!showEnviados2)}
                          className="w-full flex items-center justify-between p-4 bg-pink-50 dark:bg-pink-900/20 rounded-2xl border border-pink-100 dark:border-pink-900/30 active:scale-[0.98] transition-all"
                        >
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-pink-100 dark:bg-pink-900/50 flex items-center justify-center text-pink-600 dark:text-pink-400">
                              <Send className="w-4 h-4" />
                            </div>
                            <span className="font-bold text-pink-700 dark:text-pink-300">Pedidos Enviados 2 ({enviados2Orders.length})</span>
                          </div>
                          <div className="text-pink-400">
                            {(showEnviados2 || search.trim().length > 0) ? <ChevronDown className="w-5 h-5" /> : <ChevronRight className="w-5 h-5" />}
                          </div>
                        </button>
                        
                        <AnimatePresence>
                          {(showEnviados2 || search.trim().length > 0) && (
                            <motion.div
                              initial={{ height: 0, opacity: 0 }}
                              animate={{ height: 'auto', opacity: 1 }}
                              exit={{ height: 0, opacity: 0 }}
                              className="overflow-hidden space-y-3 mt-4"
                            >
                              {enviados2Orders.map(renderOrderCard)}
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </div>
                    )}
                  </>
                )}
              </section>
            </motion.div>
          )}

          {activeTab === 'ingreso' && (
            <motion.div
              key="ingreso"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="px-6 py-10 space-y-10"
            >
              <div className="text-center space-y-4">
                <div className="w-20 h-20 bg-blue-500/10 rounded-[2rem] flex items-center justify-center text-blue-600 mx-auto shadow-sm rotate-3">
                  <FileText className="w-10 h-10" />
                </div>
                <div>
                  <h2 className="text-2xl font-black tracking-tight text-gray-800 dark:text-white">Ingreso de Mercadería</h2>
                  <p className="text-sm text-gray-500 dark:text-gray-400 mt-2 max-w-[280px] mx-auto leading-relaxed">
                    Escanea o pega los productos que están llegando para darlos de alta.
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 gap-4">
                <button
                  onClick={handleScanClick}
                  disabled={scanning}
                  className="group relative overflow-hidden bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 p-6 rounded-[2rem] text-left transition-all active:scale-[0.98] shadow-sm hover:shadow-md disabled:opacity-50"
                >
                  <div className="flex items-center gap-5">
                    <div className="w-14 h-14 bg-blue-600 rounded-2xl flex items-center justify-center text-white shadow-lg shadow-blue-500/30">
                      <Camera className="w-7 h-7" />
                    </div>
                    <div>
                      <h3 className="font-bold text-lg dark:text-white">Cámara / Fotos</h3>
                      <p className="text-xs text-gray-500 dark:text-gray-400">Saca una foto al Remito o Factura</p>
                    </div>
                  </div>
                </button>

                <button
                  onClick={handleImportClick}
                  disabled={scanning}
                  className="group relative overflow-hidden bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 p-6 rounded-[2rem] text-left transition-all active:scale-[0.98] shadow-sm hover:shadow-md disabled:opacity-50"
                >
                  <div className="flex items-center gap-5">
                    <div className="w-14 h-14 bg-indigo-600 rounded-2xl flex items-center justify-center text-white shadow-lg shadow-indigo-500/30">
                      <FileUp className="w-7 h-7" />
                    </div>
                    <div>
                      <h3 className="font-bold text-lg dark:text-white">Subir Archivo</h3>
                      <p className="text-xs text-gray-500 dark:text-gray-400">Selecciona un PDF o Imagen desde el móvil</p>
                    </div>
                  </div>
                </button>

                <button
                  onClick={() => handlePasteTextClick('arrival')}
                  disabled={scanning}
                  className="group relative overflow-hidden bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 p-6 rounded-[2rem] text-left transition-all active:scale-[0.98] shadow-sm hover:shadow-md disabled:opacity-50"
                >
                  <div className="flex items-center gap-5">
                    <div className="w-14 h-14 bg-purple-600 rounded-2xl flex items-center justify-center text-white shadow-lg shadow-purple-500/30">
                      <FilePlus className="w-7 h-7" />
                    </div>
                    <div>
                      <h3 className="font-bold text-lg dark:text-white">Pegar Texto</h3>
                      <p className="text-xs text-gray-500 dark:text-gray-400">Copia y pega desde el bloc de notas</p>
                    </div>
                  </div>
                </button>
              </div>

              <div className="bg-amber-500/5 border border-amber-500/10 rounded-2xl p-4 flex gap-3">
                 <Settings className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
                 <p className="text-[10px] text-amber-700 dark:text-amber-400 leading-tight">
                    <b>Tip:</b> Asegúrate de tener buena luz al sacar la foto para que la IA detecte todos los códigos correctamente.
                 </p>
              </div>
            </motion.div>
          )}

          {activeTab === 'configuracion' && (
            <motion.div
              key="configuracion"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              className="space-y-6"
            >
              <div className="ios-card p-5">
                <h2 className="text-lg font-bold mb-4 flex items-center justify-between">
                  <div className="flex items-center gap-2 flex-1"><Settings className="w-5 h-5 text-[var(--accent)]" /> Ajustes</div>
                  <button
                    onClick={toggleTheme}
                    className={`relative w-12 h-7 rounded-full transition-all duration-300 flex items-center px-1 shrink-0 ${darkMode ? 'bg-blue-600' : 'bg-gray-200'}`}
                  >
                    <motion.div
                      animate={{ x: darkMode ? 20 : 0 }}
                      transition={{ type: "spring", stiffness: 500, damping: 30 }}
                      className="w-5 h-5 bg-white rounded-full shadow-sm flex items-center justify-center"
                    >
                      {darkMode ? <Moon className="w-3 h-3 text-blue-600" /> : <Sun className="w-3 h-3 text-amber-500" />}
                    </motion.div>
                  </button>
                </h2>

                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      WhatsApp Predeterminado
                    </label>
                    <input
                      type="text"
                      value={defaultPhone}
                      onChange={(e) => savePhone(e.target.value)}
                      placeholder="Ej: +5491122334455"
                      className="w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3"
                    />
                    <p className="text-xs text-gray-500 mt-1">Si está vacío, elegirás a quién enviar cada vez.</p>
                  </div>

                  {/* Removed Gemini API Key input as we use local PC motor now */}

                  <div className="pt-2 border-t border-gray-100 mt-4">
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Supabase URL
                    </label>
                    <input
                      type="text"
                      value={supaUrl}
                      onChange={(e) => saveSupaUrl(e.target.value)}
                      placeholder="https://your-project.supabase.co"
                      className="w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3"
                    />
                  </div>

                  <div className="pt-2">
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Supabase Anon Key
                    </label>
                    <input
                      type="password"
                      value={supaKey}
                      onChange={(e) => saveSupaKey(e.target.value)}
                      placeholder="your-anon-key"
                      className="w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3"
                    />
                    <p className="text-xs text-orange-500 mt-2 font-medium">⚠️ Tras cambiar estos datos, recarga la aplicación para aplicar la conexión.</p>
                  </div>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Sidebar Overlay */}
      <AnimatePresence>
        {showSidebar && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40"
              onClick={() => setShowSidebar(false)}
            />
            <motion.div
              initial={{ x: '-100%' }}
              animate={{ x: 0 }}
              exit={{ x: '-100%' }}
              transition={{ type: "spring", damping: 25, stiffness: 200 }}
              className="fixed top-0 left-0 bottom-0 w-[300px] bg-white dark:bg-[#1c1c1e] z-50 shadow-2xl flex flex-col rounded-r-[32px] overflow-hidden"
            >
              <div className="p-8 pb-6 flex justify-between items-center">
                <div>
                  <span className="font-black text-2xl tracking-tighter text-[var(--accent)]">Peucar</span>
                  <p className="text-[10px] font-bold text-gray-400 dark:text-gray-500 uppercase tracking-widest mt-1">SISTEMA DE GESTIÓN</p>
                </div>
                <button
                  onClick={() => setShowSidebar(false)}
                  className="p-2 bg-gray-100 dark:bg-gray-800 rounded-full text-gray-500 transition-transform active:scale-90"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="flex-1 px-4 py-2 space-y-1">
                <div className="text-[10px] font-bold text-gray-400 px-4 py-2 uppercase tracking-widest">Navegación</div>
                <button
                  onClick={() => { setActiveTab('ingreso'); setShowSidebar(false); }}
                  className={`sidebar-item w-full flex items-center gap-4 px-4 py-4 rounded-2xl transition-all ${activeTab === 'ingreso' ? 'active' : 'text-gray-600 dark:text-gray-400 hover:bg-black/5'}`}
                >
                  <Camera className="w-5 h-5" />
                  <span className="text-sm">Ingreso (Scanner)</span>
                </button>
                <button
                  onClick={() => { setActiveTab('pedidos'); setShowSidebar(false); }}
                  className={`sidebar-item w-full flex items-center gap-4 px-4 py-4 rounded-2xl transition-all ${activeTab === 'pedidos' ? 'active' : 'text-gray-600 dark:text-gray-400 hover:bg-black/5'}`}
                >
                  <Package className="w-5 h-5" />
                  <span className="text-sm">Pedidos</span>
                </button>
                <div className="pt-4 text-[10px] font-bold text-gray-400 px-4 py-2 uppercase tracking-widest">Mantenimiento</div>
                <button
                  onClick={() => { setActiveTab('configuracion'); setShowSidebar(false); }}
                  className={`sidebar-item w-full flex items-center gap-4 px-4 py-4 rounded-2xl transition-all ${activeTab === 'configuracion' ? 'active' : 'text-gray-600 dark:text-gray-400 hover:bg-black/5'}`}
                >
                  <Settings className="w-5 h-5" />
                  <span className="text-sm">Configuración</span>
                </button>
              </div>

              <div className="p-8 border-t border-gray-100 dark:border-gray-800 flex items-center justify-between">
                <div className="bg-gray-50 dark:bg-gray-800/50 p-4 rounded-2xl flex items-center gap-3 flex-1">
                  <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl flex items-center justify-center text-white font-bold shadow-lg shadow-blue-500/20">
                    {defaultPhone ? defaultPhone.slice(-2) : 'P'}
                  </div>
                  <div>
                    <p className="text-xs font-bold">Repartidor Activo</p>
                    <p className="text-[10px] text-gray-500">Sesión en línea</p>
                  </div>
                </div>
                <button
                  onClick={toggleTheme}
                  className="ml-4 p-3 bg-gray-50 dark:bg-gray-800/50 rounded-2xl text-gray-600 dark:text-gray-400 active:scale-90 transition-all"
                >
                  {darkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
                </button>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* Hidden File Input */}
      <input
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        ref={fileInputRef}
        onChange={handleFileSelect}
      />
      <input
        type="file"
        accept="application/pdf,image/*"
        className="hidden"
        ref={pdfInputRef}
        onChange={handleFileSelect}
      />

      {/* Review Modal for PDF Import */}
      <AnimatePresence>
        {showReviewModal && reviewOrders && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[60] bg-black/60 backdrop-blur-md flex items-center justify-center p-4"
          >
            <motion.div
              initial={{ scale: 0.9, y: 20 }}
              animate={{ scale: 1, y: 0 }}
              className="bg-white dark:bg-[#1c1c1e] rounded-[2.5rem] w-full max-w-5xl max-h-[90vh] overflow-hidden flex flex-col shadow-2xl"
            >
              <div className="p-6 border-b border-gray-100 dark:border-gray-800 flex justify-between items-center bg-white dark:bg-[#1c1c1e]">
                <div>
                  <h3 className="text-xl font-extrabold tracking-tight">{reviewMetadata ? `Ingreso: ${reviewMetadata.tipo}` : 'Revisar Pedidos'}</h3>
                  {reviewMetadata && (
                    <p className="text-[10px] font-bold text-blue-500 uppercase tracking-widest mt-0.5">
                      {reviewMetadata.numero} • {reviewMetadata.monto}
                    </p>
                  )}
                </div>
                <button onClick={() => { setShowReviewModal(false); setReviewMetadata(null); }} className="p-2 bg-gray-100 dark:bg-white/5 rounded-full hover:bg-gray-200 transition-all">
                  <X className="w-5 h-5 text-gray-800 dark:text-white" />
                </button>
              </div>

              {/* SPLIT VIEW START */}
              <div className="flex-1 overflow-hidden flex flex-col md:flex-row">
                
                {/* ─── LEFT: IMAGE PREVIEW ─── */}
                <div className="hidden md:flex md:w-[45%] bg-gray-100 dark:bg-black/40 border-r border-gray-100 dark:border-gray-800 items-center justify-center p-6 overflow-auto">
                    {scanPreview ? (
                      <div className="relative group max-w-full">
                        <img 
                          src={scanPreview} 
                          alt="Invoice Scan" 
                          className="w-full h-auto rounded-xl shadow-2xl transition-transform cursor-zoom-in"
                        />
                        <div className="absolute top-4 left-4 bg-black/50 backdrop-blur px-3 py-1.5 rounded-lg text-white text-[10px] font-bold uppercase tracking-widest opacity-0 group-hover:opacity-100 transition-opacity">
                          Vista Original
                        </div>
                      </div>
                    ) : (
                      <div className="flex flex-col items-center text-gray-400 gap-4">
                        <Camera size={48} className="opacity-20" />
                        <p className="text-xs font-medium">No hay imagen para mostrar</p>
                      </div>
                    )}
                </div>

                {/* ─── RIGHT: DATA FORM ─── */}
                <div className="flex-1 overflow-y-auto p-6 md:p-8 space-y-6 bg-gray-50/30 dark:bg-transparent">
                  <div className="mb-2">
                    <p className="text-xs font-bold text-blue-600 dark:text-blue-400 uppercase tracking-widest px-1">Verificación de datos</p>
                    <p className="text-sm text-gray-500 mt-1 px-1">Corrige cualquier dato que la IA no haya detectado bien.</p>
                  </div>

                  {reviewOrders.map((ped, idx) => (
                    <div key={idx} className="bg-white dark:bg-white/5 p-6 rounded-[2rem] space-y-5 border border-gray-100 dark:border-gray-800 shadow-sm transition-all hover:shadow-md">
                      
                      {/* Cabecera del pedido / Datos Generales */}
                      <div className="flex flex-col sm:flex-row gap-4">
                        <div className="flex-1">
                          <label className="block text-[10px] font-extrabold text-gray-400 dark:text-gray-500 uppercase mb-2 ml-1 tracking-widest">Proveedor / Pedido</label>
                          <div className="relative group">
                            <Package className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 group-focus-within:text-blue-500 transition-colors" />
                            <input
                              className="w-full pl-11 pr-4 py-3 bg-gray-50 dark:bg-gray-900/50 border border-transparent focus:border-blue-500/30 dark:focus:border-blue-500/50 rounded-2xl text-sm font-bold outline-none ring-0 focus:ring-4 ring-blue-500/10 transition-all uppercase"
                              value={ped.proveedor}
                              onChange={(e) => handleReviewOrderChange(idx, 'proveedor', e.target.value)}
                            />
                          </div>
                        </div>
                        <div className="sm:w-40">
                          <label className="block text-[10px] font-extrabold text-gray-400 dark:text-gray-500 uppercase mb-2 ml-1 tracking-widest tracking-widest">Fecha</label>
                          <div className="relative group">
                            <Calendar className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 group-focus-within:text-blue-500 transition-colors" />
                            <input
                              className="w-full pl-11 pr-4 py-3 bg-gray-50 dark:bg-gray-900/50 border border-transparent focus:border-blue-500/30 dark:focus:border-blue-500/50 rounded-2xl text-sm font-bold outline-none ring-0 focus:ring-4 ring-blue-500/10 transition-all"
                              value={ped.fecha}
                              onChange={(e) => handleReviewOrderChange(idx, 'fecha', e.target.value)}
                            />
                          </div>
                        </div>
                      </div>

                      {/* Artículos Editables */}
                      <div className="space-y-3">
                        <div className="flex justify-between items-center px-1">
                          <p className="text-[10px] font-extrabold text-gray-400 dark:text-gray-500 uppercase tracking-widest">Artículos Detectados ({ped.articulos.length})</p>
                          {!reviewMetadata && <p className="text-[9px] text-blue-500 font-bold uppercase">Editable</p>}
                        </div>
                        
                        <div className="space-y-3 pb-2">
                          {ped.articulos.map((art, aidx) => (
                            <div 
                              key={aidx}
                              className={`flex flex-col sm:flex-row items-stretch sm:items-center gap-3 p-4 rounded-2xl border transition-all ${
                                art.llegado 
                                  ? "bg-green-500/5 border-green-500/20 dark:border-green-500/10" 
                                  : "bg-gray-50/50 dark:bg-gray-900/50 border-gray-100 dark:border-gray-800"
                              }`}
                            >
                              <div className="flex items-center gap-3 flex-1 min-w-0">
                                <button 
                                  onClick={() => handleToggleLlegado(idx, aidx)}
                                  className={`w-6 h-6 flex-shrink-0 rounded-full flex items-center justify-center border transition-all ${
                                    art.llegado ? 'bg-green-500 border-green-500 text-white shadow-sm shadow-green-500/30' : 'border-gray-300 dark:border-gray-700 hover:border-blue-400'
                                  }`}
                                >
                                  {art.llegado && <Check className="w-4 h-4 stroke-[3]" />}
                                </button>
                                
                                <div className="flex flex-col flex-1 min-w-0">
                                  <input
                                    className={`bg-transparent p-0 text-sm font-bold border-none outline-none focus:ring-0 ${art.llegado ? 'text-green-700 dark:text-green-400' : 'dark:text-white'}`}
                                    value={art.codigo}
                                    placeholder="Código"
                                    onChange={(e) => handleReviewItemChange(idx, aidx, 'codigo', e.target.value.toUpperCase())}
                                  />
                                  <input
                                    className="bg-transparent p-0 text-[10px] text-gray-400 border-none outline-none focus:ring-0 truncate w-full"
                                    value={art.descripcion || '-'}
                                    placeholder="Descripción"
                                    onChange={(e) => handleReviewItemChange(idx, aidx, 'descripcion', e.target.value)}
                                  />
                                </div>
                              </div>
                              
                              <div className="flex items-center gap-2">
                                <div className="flex items-center gap-1 bg-white/40 dark:bg-black/20 rounded-xl px-2 py-1">
                                  <span className="text-[10px] font-bold text-gray-400">Qty:</span>
                                  <input
                                    type="number"
                                    step="any"
                                    className="w-16 bg-transparent border-none outline-none focus:ring-0 text-sm font-black text-center"
                                    value={art.cantidad}
                                    onChange={(e) => handleReviewItemChange(idx, aidx, 'cantidad', e.target.value)}
                                  />
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              {/* SPLIT VIEW END */}

              <div className="p-6 bg-white dark:bg-[#1c1c1e] border-t border-gray-100 dark:border-gray-800 shadow-[0_-10px_20px_rgba(0,0,0,0.1)]">
                <button
                  onClick={handleConfirmImport}
                  disabled={loading}
                  className={`w-full h-18 py-4 rounded-3xl font-black text-lg shadow-xl flex items-center justify-center gap-4 active:scale-[0.98] transition-all disabled:opacity-50 ${reviewMetadata ? 'bg-green-600 shadow-green-500/20 text-white' : 'bg-blue-600 shadow-blue-500/20 text-white'}`}
                >
                  {loading ? (
                    <div className="w-6 h-6 border-3 border-white/30 border-t-white rounded-full animate-spin"></div>
                  ) : (
                    <>
                      <CheckCircle2 className="w-7 h-7" />
                      <span>{reviewMetadata ? 'CONFIRMAR INGRESO' : 'GUARDAR PEDIDOS'}</span>
                    </>
                  )}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Paste Text Modal */}
      <AnimatePresence>
        {showPasteModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-end sm:items-center justify-center p-4"
          >
            <motion.div
              initial={{ y: '100%' }}
              animate={{ y: 0 }}
              exit={{ y: '100%' }}
              className="ios-card w-full max-w-lg bg-white dark:bg-gray-900 p-6 overflow-y-auto max-h-[90vh]"
            >
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-xl font-bold">Pegar Texto de Pedido</h2>
                <button onClick={() => setShowPasteModal(false)} className="p-2 text-gray-400">
                  <X className="w-6 h-6" />
                </button>
              </div>

              <div className="space-y-4">

                <div>
                  <label className="block text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-1.5">Texto del Pedido</label>
                  <textarea
                    placeholder={"Pega el texto del pedido. Ejemplos:\n1103P8 X 1\n04/115/010 2\n9818914980 X 3"}
                    className="w-full h-52 bg-black/5 dark:bg-white/5 border border-transparent rounded-2xl px-4 py-3 text-sm outline-none focus:ring-2 ring-purple-500/20 resize-none font-mono"
                    value={pasteData.rawText}
                    onChange={(e) => setPasteData({ ...pasteData, rawText: e.target.value })}
                  />
                  <p className="text-[10px] text-gray-400 italic px-2 mt-1">
                    Formato: CODIGO X CANTIDAD o CODIGO CANTIDAD, un articulo por linea.
                  </p>
                </div>

                <button
                  onClick={handlePasteImport}
                  disabled={!pasteData.rawText.trim()}
                  className="w-full h-14 bg-purple-600 text-white rounded-2xl font-bold shadow-lg shadow-purple-500/20 disabled:opacity-50 disabled:grayscale transition-all active:scale-95 flex items-center justify-center gap-3"
                >
                  <FileText className="w-5 h-5" />
                  Procesar Texto del Pedido
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Scanner Overlay */}
      <AnimatePresence>
        {scanning && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-6"
          >
            <div className="bg-white dark:bg-[#1c1c1e] p-8 rounded-[2.5rem] w-full max-w-sm flex flex-col items-center text-center shadow-2xl border border-gray-100 dark:border-gray-800">
              {scanPreview ? (
                <div className="w-32 h-44 mb-6 rounded-2xl overflow-hidden shadow-lg border border-gray-200 dark:border-gray-700 relative bg-gray-100 dark:bg-black/20">
                  <img src={scanPreview} alt="Preview" className="w-full h-full object-cover opacity-60" />
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
                  </div>
                </div>
              ) : (
                <div className="w-16 h-16 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mb-6"></div>
              )}
              <h3 className="text-xl font-bold mb-2">{scanStatus}</h3>
              <p className="text-center text-gray-500 text-sm px-4">
                {scanStatus === 'Esperando a la PC...' 
                  ? 'La PC ha recibido la imagen y está por comenzar.' 
                  : scanStatus === 'PC Trabajando...'
                  ? 'Nuestra IA está leyendo los datos localmente.'
                  : (scanStatus === 'Subiendo imagen...' ? 'Enviando foto a la nube...' : 'Preparando proceso móvil.')}
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </main>
  )
}

function StatusBadge({ status, onClick }) {
  const normalizedStatus = status ? (status.charAt(0).toUpperCase() + status.slice(1).toLowerCase()) : 'Pendiente'
  const colors = {
    'Borrador': 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
    'Completado': 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
    'Pendiente': 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
    'Parcial': 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
    'Enviado': 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
    'Enviados 2': 'bg-pink-100 text-pink-700 dark:bg-pink-900/30 dark:text-pink-400',
    'Cancelado': 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  }
  return (
    <span
      onClick={onClick}
      className={`text-[10px] font-bold px-2 py-1 rounded-full uppercase tracking-tighter cursor-pointer select-none transition-opacity hover:opacity-80 ${colors[normalizedStatus] || 'bg-gray-100'} ${onClick ? 'ring-1 ring-offset-1 ring-current/20' : ''}`}
    >
      {normalizedStatus}
    </span>
  )
}

function StatusPickerDropdown({ currentStatus, onSelect, onClose }) {
  const ESTADOS = [
    { label: 'Borrador',   color: 'text-orange-600 dark:text-orange-400', bg: 'hover:bg-orange-50 dark:hover:bg-orange-900/20' },
    { label: 'Pendiente',  color: 'text-amber-600  dark:text-amber-400',  bg: 'hover:bg-amber-50  dark:hover:bg-amber-900/20' },
    { label: 'Enviado',    color: 'text-purple-600 dark:text-purple-400', bg: 'hover:bg-purple-50 dark:hover:bg-purple-900/20' },
    { label: 'Enviados 2', color: 'text-pink-600   dark:text-pink-400',   bg: 'hover:bg-pink-50   dark:hover:bg-pink-900/20' },
    { label: 'Parcial',   color: 'text-blue-600   dark:text-blue-400',   bg: 'hover:bg-blue-50   dark:hover:bg-blue-900/20' },
    { label: 'Completado', color: 'text-green-600  dark:text-green-400',  bg: 'hover:bg-green-50  dark:hover:bg-green-900/20' },
    { label: 'Cancelado',  color: 'text-red-600    dark:text-red-400',    bg: 'hover:bg-red-50    dark:hover:bg-red-900/20' },
  ]

  return (
    <>
      {/* Backdrop para cerrar al tocar fuera */}
      <div className="fixed inset-0 z-40" onClick={onClose} />
      <div className="absolute right-0 top-full mt-1 z-50 bg-white dark:bg-[#2c2c2e] rounded-2xl shadow-xl border border-gray-100 dark:border-white/10 overflow-hidden w-36 py-1">
        {ESTADOS.map(({ label, color, bg }) => (
          <button
            key={label}
            onClick={(e) => { e.stopPropagation(); onSelect(label) }}
            className={`w-full flex items-center gap-2.5 px-3 py-2.5 text-left transition-colors ${bg} ${label === currentStatus ? 'opacity-40 pointer-events-none' : ''}`}
          >
            <span className={`w-2 h-2 rounded-full flex-shrink-0 ${color.replace('text-', 'bg-').split(' ')[0]}`} />
            <span className={`text-xs font-bold ${color}`}>{label}</span>
            {label === currentStatus && <span className="ml-auto text-[9px] text-gray-400">actual</span>}
          </button>
        ))}
      </div>
    </>
  )
}
