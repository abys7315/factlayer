import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useSearchParams, useNavigate, Link } from 'react-router-dom';
import {
  IconNetwork,
  IconSearch,
  IconFilter,
  IconEye,
  IconRefreshCw,
  IconSparkles,
  IconShieldCheck,
  IconAlertTriangle,
  IconClock,
  IconCheckCircle,
  IconInfo,
  IconFileText,
  IconZoomIn,
  IconZoomOut,
  IconMaximize,
  IconCompass,
  IconX,
  IconChevronRight,
  IconLayers,
  IconExternalLink,
} from './Icons';
import { api } from '../api/client';
import ReasoningTraceModal from './ReasoningTraceModal';

export default function KnowledgeGraphView() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  // Query parameters
  const paramFactId = searchParams.get('fact_id');
  const paramEntity = searchParams.get('entity') || searchParams.get('entity_name');
  const paramDocId = searchParams.get('doc_id') || searchParams.get('document_id');
  const paramType = searchParams.get('type') || searchParams.get('relationship_type');
  const paramPreset = searchParams.get('preset');
  const paramRelId = searchParams.get('relationship_id') || searchParams.get('rel_id');
  const paramFrom = searchParams.get('from');

  // State
  const [graphData, setGraphData] = useState({ nodes: [], edges: [], stats: {} });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [entitiesList, setEntitiesList] = useState([]);
  const [entitySearchQuery, setEntitySearchQuery] = useState('');
  const [isEntityDropdownOpen, setIsEntityDropdownOpen] = useState(false);

  // Document filter dropdown state
  const [documentsList, setDocumentsList] = useState([]);
  const [docSearchQuery, setDocSearchQuery] = useState('');
  const [isDocDropdownOpen, setIsDocDropdownOpen] = useState(false);

  // Active filters
  const [activeTypeFilter, setActiveTypeFilter] = useState(paramType || 'ALL');
  const [activePreset, setActivePreset] = useState(paramPreset || (paramFactId ? 'focus' : 'all'));
  const [nodeTypeVisibility, setNodeTypeVisibility] = useState({
    entity: true,
    document: true,
    fact: true,
  });

  // Sync state with URL params
  useEffect(() => {
    setActivePreset(paramPreset || (paramFactId ? 'focus' : 'all'));
  }, [paramPreset, paramFactId]);

  useEffect(() => {
    setActiveTypeFilter(paramType || 'ALL');
  }, [paramType]);

  // Selected item for the Inspector panel
  const [selectedNode, setSelectedNode] = useState(null);
  const [selectedEdge, setSelectedEdge] = useState(null);
  const [hoveredNodeId, setHoveredNodeId] = useState(null);

  // Modal state for Reasoning Trace
  const [activeReasoningRel, setActiveReasoningRel] = useState(null);

  // Viewport zoom and pan state
  const [transform, setTransform] = useState({ x: 450, y: 320, scale: 0.95 });
  const [isDraggingCanvas, setIsDraggingCanvas] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [draggedNodeId, setDraggedNodeId] = useState(null);
  const [layoutSpacing, setLayoutSpacing] = useState(1.15);

  // Node position map: { [nodeId]: { x, y, vx, vy, isFixed } }
  const [nodePositions, setNodePositions] = useState({});
  const positionsRef = useRef({});
  const svgRef = useRef(null);
  const simulationRef = useRef(null);

  // Keep positionsRef synced
  useEffect(() => {
    positionsRef.current = nodePositions;
  }, [nodePositions]);

  // Fetch available entities and documents for search / autocomplete
  useEffect(() => {
    async function loadMetadata() {
      try {
        const [entRes, docRes] = await Promise.all([
          api.getGraphEntities(50).catch(() => ({ items: [] })),
          api.listDocuments(0, 100).catch(() => ({ items: [] })),
        ]);
        if (entRes?.items) setEntitiesList(entRes.items);
        if (docRes?.items) setDocumentsList(docRes.items);
      } catch (e) {
        console.warn('Failed to load graph metadata:', e);
      }
    }
    loadMetadata();
  }, []);

  // Fetch graph data from backend
  const fetchGraph = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = {};
      if (paramFactId) params.fact_id = paramFactId;
      if (paramEntity) params.entity_name = paramEntity;
      if (paramDocId) params.document_id = paramDocId;
      if (paramRelId) params.relationship_id = paramRelId;
      if (activeTypeFilter !== 'ALL') params.relationship_type = activeTypeFilter;
      if (activePreset && activePreset !== 'all' && activePreset !== 'focus') {
        params.preset = activePreset;
      }

      const data = await api.getGraph(params);
      setGraphData(data);

      // Auto-select targeted edge or focused fact
      if (paramRelId && data.edges?.length > 0) {
        const targetEdge = data.edges.find((e) => e.id === paramRelId || e.rel_id === paramRelId);
        if (targetEdge) {
          setSelectedEdge(targetEdge);
          setSelectedNode(null);
        }
      } else if (data.focused_id) {
        const focusNode = data.nodes.find((n) => n.id === data.focused_id);
        if (focusNode) {
          setSelectedNode(focusNode);
          setSelectedEdge(null);
        }
      } else if (data.nodes.length > 0 && !selectedNode && !selectedEdge) {
        // Select an entity or first fact
        const initial = data.nodes.find((n) => n.type === 'entity') || data.nodes[0];
        setSelectedNode(initial);
      }

      // Initialize physical layout simulation for nodes with configured spacing
      initSimulation(data.nodes, data.edges, data.focused_id, paramRelId, layoutSpacing);
    } catch (err) {
      console.error('Error fetching graph:', err);
      setError(err.message || 'Failed to construct knowledge graph.');
    } finally {
      setLoading(false);
    }
  }, [paramFactId, paramEntity, paramDocId, paramRelId, activeTypeFilter, activePreset, layoutSpacing]);

  useEffect(() => {
    fetchGraph();
  }, [fetchGraph]);

  const fitToViewRef = useRef(null);

  // Physical force-directed layout simulation with strict rectangular collision prevention
  const initSimulation = useCallback(
    (nodes, edges, focusedId, relId, spacingMult = 1.15) => {
      if (simulationRef.current) cancelAnimationFrame(simulationRef.current);

      const positions = {};
      const centerX = 0;
      const centerY = 0;

      const targetEdge = relId ? edges.find((e) => e.id === relId || e.rel_id === relId) : null;
      const relSourceId = targetEdge?.source;
      const relTargetId = targetEdge?.target;

      const entityNodes = nodes.filter((n) => n.type === 'entity');
      const docNodes = nodes.filter((n) => n.type === 'document');
      const factNodes = nodes.filter((n) => n.type === 'fact');

      // 1. Entities in inner hub
      entityNodes.forEach((node, idx) => {
        const angle = (idx / Math.max(entityNodes.length, 1)) * 2 * Math.PI;
        const radius = entityNodes.length > 1 ? 210 * spacingMult : 0;
        positions[node.id] = {
          x: centerX + Math.cos(angle) * radius,
          y: centerY + Math.sin(angle) * radius,
          vx: 0,
          vy: 0,
          isFixed: false,
        };
      });

      // 2. Documents on left perimeter arc
      docNodes.forEach((node, idx) => {
        const docX = centerX - 540 * spacingMult;
        const docY = centerY + (idx - (docNodes.length - 1) / 2) * 115 * spacingMult;
        positions[node.id] = {
          x: docX,
          y: docY,
          vx: 0,
          vy: 0,
          isFixed: false,
        };
      });

      // 3. Facts arranged in staggered concentric rings
      const factsPerRing = [6, 10, 14, 18, 22, 26];
      let ringIndex = 0;
      let countInRing = 0;

      factNodes.forEach((node) => {
        const isRelPair = node.id === relSourceId || node.id === relTargetId;
        const isFocused = node.id === focusedId;

        let initX, initY;

        if (node.id === relSourceId) {
          initX = centerX - 210 * spacingMult;
          initY = centerY;
        } else if (node.id === relTargetId) {
          initX = centerX + 210 * spacingMult;
          initY = centerY;
        } else if (isFocused) {
          initX = centerX;
          initY = centerY;
        } else {
          const baseRadius = 290 + ringIndex * 170;
          const radius = baseRadius * spacingMult;
          const maxInRing = factsPerRing[ringIndex] || 20;
          const angleOffset = (ringIndex % 2) * (Math.PI / maxInRing);
          const angle = (countInRing / maxInRing) * 2 * Math.PI + angleOffset;

          initX = centerX + Math.cos(angle) * radius + (Math.random() - 0.5) * 20;
          initY = centerY + Math.sin(angle) * radius + (Math.random() - 0.5) * 20;

          countInRing++;
          if (countInRing >= maxInRing) {
            ringIndex++;
            countInRing = 0;
          }
        }

        positions[node.id] = {
          x: initX,
          y: initY,
          vx: 0,
          vy: 0,
          isFixed: isRelPair || isFocused,
        };
      });

      // Node half-extents for bounding box collision (240x86 fact, 180x58 doc, 50r entity)
      const getNodeExtents = (id) => {
        const n = nodes.find((item) => item.id === id);
        if (!n) return { hw: 126, hh: 48 };
        if (n.type === 'fact') return { hw: 128, hh: 50 };
        if (n.type === 'document') return { hw: 96, hh: 34 };
        return { hw: 56, hh: 56 };
      };

      const nodeIds = nodes.map((n) => n.id);
      const kRepel = Math.max(260000, nodes.length * 8000) * spacingMult;
      const kAttract = 0.04;

      // Simulation ticks: 85 physics + 25 pure collision relaxation
      const totalTicks = 110;
      for (let step = 0; step < totalTicks; step++) {
        const alpha = Math.max(1 - step / 85, 0);
        const isRelaxation = step >= 85;

        if (!isRelaxation) {
          // 1. Coulomb Repulsion
          for (let i = 0; i < nodeIds.length; i++) {
            const idA = nodeIds[i];
            const posA = positions[idA];
            if (!posA) continue;

            for (let j = i + 1; j < nodeIds.length; j++) {
              const idB = nodeIds[j];
              const posB = positions[idB];
              if (!posB) continue;

              const dx = posA.x - posB.x;
              const dy = posA.y - posB.y;
              const distSq = dx * dx + dy * dy + 400;
              const dist = Math.sqrt(distSq);
              const force = (kRepel / distSq) * alpha;

              const fx = (dx / dist) * force;
              const fy = (dy / dist) * force;

              if (!posA.isFixed) {
                posA.x += fx;
                posA.y += fy;
              }
              if (!posB.isFixed) {
                posB.x -= fx;
                posB.y -= fy;
              }
            }
          }

          // 2. Spring Link Attraction
          edges.forEach((edge) => {
            const posA = positions[edge.source];
            const posB = positions[edge.target];
            if (!posA || !posB) return;

            const dx = posB.x - posA.x;
            const dy = posB.y - posA.y;
            const dist = Math.sqrt(dx * dx + dy * dy) || 1;
            const isCrossRel =
              edge.type === 'CONTRADICTS' ||
              edge.type === 'SUPERSEDES' ||
              edge.type === 'CORROBORATES' ||
              edge.type === 'CONTEXTUAL_DIFFERENCE';
            const targetDist = (isCrossRel ? 400 : 310) * spacingMult;
            const diff = dist - targetDist;
            const force = diff * kAttract * alpha;

            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;

            if (!posA.isFixed) {
              posA.x += fx;
              posA.y += fy;
            }
            if (!posB.isFixed) {
              posB.x -= fx;
              posB.y -= fy;
            }
          });

          // 3. Gentle Centering Gravity
          nodeIds.forEach((id) => {
            const pos = positions[id];
            if (!pos || pos.isFixed) return;
            pos.x -= pos.x * 0.003 * alpha;
            pos.y -= pos.y * 0.003 * alpha;
          });
        }

        // 4. Strict Bounding Box Collision Resolution Pass
        for (let i = 0; i < nodeIds.length; i++) {
          const idA = nodeIds[i];
          const posA = positions[idA];
          if (!posA) continue;
          const extA = getNodeExtents(idA);

          for (let j = i + 1; j < nodeIds.length; j++) {
            const idB = nodeIds[j];
            const posB = positions[idB];
            if (!posB) continue;
            const extB = getNodeExtents(idB);

            const minDx = extA.hw + extB.hw;
            const minDy = extA.hh + extB.hh;
            const dx = posA.x - posB.x;
            const dy = posA.y - posB.y;
            const absDx = Math.abs(dx);
            const absDy = Math.abs(dy);

            if (absDx < minDx && absDy < minDy) {
              const overlapX = minDx - absDx;
              const overlapY = minDy - absDy;

              if (overlapX / minDx < overlapY / minDy) {
                const sign = dx >= 0 ? 1 : -1;
                const move = overlapX;
                if (!posA.isFixed && !posB.isFixed) {
                  posA.x += sign * move * 0.5;
                  posB.x -= sign * move * 0.5;
                } else if (!posA.isFixed) {
                  posA.x += sign * move;
                } else if (!posB.isFixed) {
                  posB.x -= sign * move;
                }
              } else {
                const sign = dy >= 0 ? 1 : -1;
                const move = overlapY;
                if (!posA.isFixed && !posB.isFixed) {
                  posA.y += sign * move * 0.5;
                  posB.y -= sign * move * 0.5;
                } else if (!posA.isFixed) {
                  posA.y += sign * move;
                } else if (!posB.isFixed) {
                  posB.y -= sign * move;
                }
              }
            }
          }
        }
      }

      setNodePositions(positions);
      setTimeout(() => {
        if (fitToViewRef.current) {
          fitToViewRef.current(positions, nodes);
        }
      }, 50);
    },
    []
  );

  // Canvas zoom & pan handlers — cursor anchored zoom
  const handleWheel = (e) => {
    e.preventDefault();
    if (!svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const zoomFactor = e.deltaY < 0 ? 1.15 : 0.87;
    setTransform((prev) => {
      const newScale = Math.min(Math.max(prev.scale * zoomFactor, 0.2), 3.5);
      const graphX = (mouseX - prev.x) / prev.scale;
      const graphY = (mouseY - prev.y) / prev.scale;
      return {
        x: mouseX - graphX * newScale,
        y: mouseY - graphY * newScale,
        scale: newScale,
      };
    });
  };

  const handleMouseDownCanvas = (e) => {
    // Only drag canvas if clicked directly on SVG canvas, not on a node
    if (e.target.tagName === 'svg' || e.target.id === 'canvas-grid-bg') {
      setIsDraggingCanvas(true);
      setDragStart({ x: e.clientX - transform.x, y: e.clientY - transform.y });
    }
  };

  const handleMouseMoveCanvas = (e) => {
    if (isDraggingCanvas) {
      setTransform((prev) => ({
        ...prev,
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y,
      }));
    } else if (draggedNodeId && nodePositions[draggedNodeId]) {
      // Drag individual node
      const rect = svgRef.current.getBoundingClientRect();
      const mouseX = (e.clientX - rect.left - transform.x) / transform.scale;
      const mouseY = (e.clientY - rect.top - transform.y) / transform.scale;

      setNodePositions((prev) => ({
        ...prev,
        [draggedNodeId]: {
          ...prev[draggedNodeId],
          x: mouseX,
          y: mouseY,
          isFixed: true,
        },
      }));
    }
  };

  const handleMouseUpCanvas = () => {
    setIsDraggingCanvas(false);
    setDraggedNodeId(null);
  };

  // Zoom control buttons
  const zoomIn = () => setTransform((p) => ({ ...p, scale: Math.min(p.scale * 1.2, 3.5) }));
  const zoomOut = () => setTransform((p) => ({ ...p, scale: Math.max(p.scale / 1.2, 0.2) }));

  const resetZoom = () => {
    if (svgRef.current) {
      const rect = svgRef.current.getBoundingClientRect();
      const containerW = rect.width > 0 ? rect.width : 1100;
      const containerH = rect.height > 0 ? rect.height : 750;
      setTransform({ x: containerW / 2, y: containerH / 2, scale: 1.0 });
    } else {
      setTransform({ x: 500, y: 350, scale: 1.0 });
    }
  };

  // Filtered nodes and edges
  const visibleNodes = useMemo(() => {
    return graphData.nodes.filter((node) => {
      if (node.type === 'entity' && !nodeTypeVisibility.entity) return false;
      if (node.type === 'document' && !nodeTypeVisibility.document) return false;
      if (node.type === 'fact' && !nodeTypeVisibility.fact) return false;
      return true;
    });
  }, [graphData.nodes, nodeTypeVisibility]);

  const visibleNodeIds = useMemo(() => new Set(visibleNodes.map((n) => n.id)), [visibleNodes]);

  const visibleEdges = useMemo(() => {
    return graphData.edges.filter((edge) => {
      if (!visibleNodeIds.has(edge.source) || !visibleNodeIds.has(edge.target)) return false;
      if (activeTypeFilter !== 'ALL') {
        // Only show relationship edges matching filter (or structural edges if connected)
        if (edge.type !== activeTypeFilter && edge.type !== 'HAS_FACT' && edge.type !== 'EXTRACTED_FROM') {
          return false;
        }
      }
      return true;
    });
  }, [graphData.edges, visibleNodeIds, activeTypeFilter]);

  // Color-coded role map for fact cards based on cross-document relationship type
  const nodeRoleMap = useMemo(() => {
    const map = {};
    graphData.edges.forEach((e) => {
      if (e.type === 'CONTRADICTS') {
        map[e.source] = 'CONTRADICTS';
        map[e.target] = 'CONTRADICTS';
      } else if (e.type === 'SUPERSEDES') {
        if (!map[e.source]) map[e.source] = 'SUPERSEDES';
        if (!map[e.target]) map[e.target] = 'SUPERSEDES';
      } else if (e.type === 'CORROBORATES') {
        if (!map[e.source]) map[e.source] = 'CORROBORATES';
        if (!map[e.target]) map[e.target] = 'CORROBORATES';
      } else if (e.type === 'CONTEXTUAL_DIFFERENCE') {
        if (!map[e.source]) map[e.source] = 'CONTEXTUAL_DIFFERENCE';
        if (!map[e.target]) map[e.target] = 'CONTEXTUAL_DIFFERENCE';
      }
    });
    return map;
  }, [graphData.edges]);

  // Fit all visible nodes into current viewport
  const fitToView = useCallback(
    (overridePositions = null, overrideNodes = null) => {
      const pos = overridePositions || positionsRef.current || nodePositions;
      const nodes = overrideNodes || (visibleNodes?.length ? visibleNodes : graphData.nodes);
      if (!nodes || nodes.length === 0 || !svgRef.current) return;

      const rect = svgRef.current.getBoundingClientRect();
      const containerW = rect.width > 0 ? rect.width : 1100;
      const containerH = rect.height > 0 ? rect.height : 750;

      let minX = Infinity,
        maxX = -Infinity,
        minY = Infinity,
        maxY = -Infinity;
      let found = 0;

      nodes.forEach((n) => {
        const p = pos[n.id];
        if (p) {
          found++;
          const hw = n.type === 'fact' ? 110 : n.type === 'document' ? 80 : 55;
          const hh = n.type === 'fact' ? 42 : n.type === 'document' ? 32 : 55;
          if (p.x - hw < minX) minX = p.x - hw;
          if (p.x + hw > maxX) maxX = p.x + hw;
          if (p.y - hh < minY) minY = p.y - hh;
          if (p.y + hh > maxY) maxY = p.y + hh;
        }
      });

      if (found === 0 || !isFinite(minX) || !isFinite(maxX)) return;

      const padding = 80;
      const graphW = Math.max(maxX - minX + padding * 2, 280);
      const graphH = Math.max(maxY - minY + padding * 2, 280);

      const scaleX = containerW / graphW;
      const scaleY = containerH / graphH;
      const optimalScale = Math.min(Math.max(Math.min(scaleX, scaleY), 0.22), 1.25);

      const centerX = (minX + maxX) / 2;
      const centerY = (minY + maxY) / 2;

      setTransform({
        x: containerW / 2 - centerX * optimalScale,
        y: containerH / 2 - centerY * optimalScale,
        scale: optimalScale,
      });
    },
    [nodePositions, visibleNodes, graphData.nodes]
  );

  useEffect(() => {
    fitToViewRef.current = fitToView;
  }, [fitToView]);

  const centerOnFocused = useCallback(() => {
    const focusId = graphData.focused_id;
    let targetPos = null;
    if (focusId && nodePositions[focusId]) {
      targetPos = nodePositions[focusId];
    } else if (paramRelId && graphData.edges?.length) {
      const targetEdge = graphData.edges.find((e) => e.id === paramRelId || e.rel_id === paramRelId);
      if (targetEdge && nodePositions[targetEdge.source]) {
        targetPos = nodePositions[targetEdge.source];
      }
    } else if (selectedNode && nodePositions[selectedNode.id]) {
      targetPos = nodePositions[selectedNode.id];
    }

    if (targetPos && svgRef.current) {
      const rect = svgRef.current.getBoundingClientRect();
      const containerW = rect.width > 0 ? rect.width : 1100;
      const containerH = rect.height > 0 ? rect.height : 750;
      const targetScale = Math.max(transform.scale, 0.95);
      setTransform({
        x: containerW / 2 - targetPos.x * targetScale,
        y: containerH / 2 - targetPos.y * targetScale,
        scale: targetScale,
      });
    } else {
      fitToView();
    }
  }, [graphData, nodePositions, paramRelId, selectedNode, transform.scale, fitToView]);

  const reSimulateLayout = useCallback(
    (spacing) => {
      const s = spacing || layoutSpacing;
      if (graphData.nodes?.length > 0) {
        initSimulation(graphData.nodes, graphData.edges, graphData.focused_id, paramRelId, s);
      }
    },
    [graphData, paramRelId, layoutSpacing, initSimulation]
  );

  const handleSpacingChange = (newSpacing) => {
    setLayoutSpacing(newSpacing);
    reSimulateLayout(newSpacing);
  };

  // Color mapping for edge types
  const getEdgeStyle = (edge) => {
    switch (edge.type) {
      case 'CONTRADICTS':
        return { stroke: '#ef4444', strokeWidth: 3, strokeDasharray: 'none', labelBg: '#fee2e2', labelText: '#b91c1c' };
      case 'SUPERSEDES':
        return { stroke: '#f59e0b', strokeWidth: 2.5, strokeDasharray: 'none', labelBg: '#fef3c7', labelText: '#b45309' };
      case 'CORROBORATES':
        return { stroke: '#10b981', strokeWidth: 2.5, strokeDasharray: 'none', labelBg: '#d1fae5', labelText: '#047857' };
      case 'CONTEXTUAL_DIFFERENCE':
        return { stroke: '#3b82f6', strokeWidth: 2, strokeDasharray: 'none', labelBg: '#dbeafe', labelText: '#1d4ed8' };
      case 'EXTRACTED_FROM':
        return { stroke: '#06b6d4', strokeWidth: 1.5, strokeDasharray: '3 3', labelBg: '#cffafe', labelText: '#0e7490' };
      case 'HAS_FACT':
      default:
        return { stroke: '#8b5cf6', strokeWidth: 1.5, strokeDasharray: '4 3', labelBg: '#ede9fe', labelText: '#6d28d9' };
    }
  };

  // Preset switchers
  const handlePresetSelect = (presetName) => {
    setActivePreset(presetName);
    const newParams = new URLSearchParams(searchParams);
    if (presetName === 'all') {
      newParams.delete('preset');
      newParams.delete('type');
      newParams.delete('relationship_type');
    } else if (presetName === 'focus') {
      newParams.set('preset', 'focus');
      if (paramFactId) newParams.set('fact_id', paramFactId);
    } else {
      newParams.set('preset', presetName);
    }
    setSearchParams(newParams);
  };

  // Entity switch
  const handleEntitySelect = (entityName) => {
    setIsEntityDropdownOpen(false);
    const newParams = new URLSearchParams(searchParams);
    if (entityName) {
      newParams.set('entity', entityName);
    } else {
      newParams.delete('entity');
      newParams.delete('entity_name');
    }
    setSearchParams(newParams);
  };

  // Document switch
  const handleDocSelect = (docId) => {
    setIsDocDropdownOpen(false);
    const newParams = new URLSearchParams(searchParams);
    if (docId) {
      newParams.set('document_id', docId);
      newParams.delete('doc_id');
    } else {
      newParams.delete('document_id');
      newParams.delete('doc_id');
    }
    setSearchParams(newParams);
  };

  // Reset to global knowledge graph
  const handleResetToGlobal = () => {
    setSearchParams({});
    setActivePreset('all');
    setActiveTypeFilter('ALL');
    setSelectedNode(null);
    setSelectedEdge(null);
  };

  // Origin Tab Navigation Link
  const originTabLink = useMemo(() => {
    if (paramFrom === 'contradictions') {
      return { label: 'Contradiction Center', url: '/contradictions' };
    }
    if (paramFrom === 'timeline') {
      return { label: 'Timeline & History', url: '/timeline' };
    }
    if (paramFrom === 'relationships') {
      return { label: 'Cross-Document Relationships', url: '/relationships' };
    }
    if (paramFrom === 'documents') {
      if (paramDocId) {
        return { label: 'Document Detail', url: `/documents/${paramDocId}` };
      }
      return { label: 'Document Repository', url: '/documents' };
    }
    if (paramFrom === 'facts') {
      return { label: 'Fact Explorer', url: '/facts' };
    }
    return null;
  }, [paramFrom, paramDocId]);

  // Dynamic Context Description for Banner
  const contextDescription = useMemo(() => {
    const parts = [];
    if (originTabLink) {
      parts.push(`Tab Source: ${originTabLink.label}`);
    }
    if (paramRelId) {
      parts.push(`Target Relationship: ${paramRelId.substring(0, 8)}...`);
    } else if (activePreset && activePreset !== 'all') {
      const presetLabels = {
        contradictions: 'Contradictions Filter',
        corroborations: 'Corroborations Filter',
        supersedes: 'Supersessions Timeline',
        contextual_differences: 'Contextual Differences',
        relationships: 'All Relationships',
        focus: 'Focal Claim Subgraph',
      };
      parts.push(presetLabels[activePreset] || activePreset);
    }
    if (paramDocId) {
      const doc = documentsList.find((d) => d.id === paramDocId);
      parts.push(`Doc: ${doc ? doc.filename : paramDocId.substring(0, 8) + '...'}`);
    }
    if (paramEntity) {
      parts.push(`Entity: ${paramEntity}`);
    }
    if (paramFactId && !paramRelId) {
      parts.push(`Fact ID: ${paramFactId.substring(0, 8)}...`);
    }
    return parts.length > 0 ? parts.join(' • ') : null;
  }, [originTabLink, paramRelId, activePreset, paramDocId, documentsList, paramEntity, paramFactId]);

  // Connected count for hovered node
  const isNodeDimmed = (nodeId) => {
    if (!hoveredNodeId) return false;
    if (nodeId === hoveredNodeId) return false;
    const isNeighbor = graphData.edges.some(
      (e) => (e.source === hoveredNodeId && e.target === nodeId) || (e.target === hoveredNodeId && e.source === nodeId)
    );
    return !isNeighbor;
  };

  return (
    <div className="kg-page">
      {/* Top Controls Toolbar */}
      <div className="kg-toolbar">
        {/* Left: Brand & Scope */}
        <div className="kg-brand">
          <div className="kg-brand-icon">
            <IconNetwork style={{ width: 20, height: 20 }} />
          </div>
          <div>
            <h1 className="kg-brand-title">
              Knowledge Graph Explorer
              {graphData.focused_entity && (
                <span className="kg-entity-chip">
                  {graphData.focused_entity}
                </span>
              )}
            </h1>
            <p className="kg-brand-subtitle">
              {graphData.stats?.fact_count || 0} Grounded Claims &bull; {graphData.stats?.total_relationships || 0} Cross-Document Relationships
            </p>
          </div>
        </div>

        {/* Center: Presets & Quick Filter Tabs */}
        <div className="kg-preset-group">
          <button
            type="button"
            className={`kg-preset-btn ${activePreset === 'all' ? 'active-all' : ''}`}
            onClick={() => handlePresetSelect('all')}
          >
            All
          </button>

          {paramFactId && (
            <button
              type="button"
              className={`kg-preset-btn ${activePreset === 'focus' ? 'active-focus' : ''}`}
              onClick={() => handlePresetSelect('focus')}
            >
              Focal Subgraph
            </button>
          )}

          <button
            type="button"
            className={`kg-preset-btn ${activePreset === 'contradictions' ? 'active-contradictions' : ''}`}
            onClick={() => handlePresetSelect('contradictions')}
          >
            <span className="kg-dot" style={{ background: '#f43f5e' }}></span>
            Contradictions ({graphData.stats?.contradictions ?? '0'})
          </button>

          <button
            type="button"
            className={`kg-preset-btn ${activePreset === 'supersedes' ? 'active-supersedes' : ''}`}
            onClick={() => handlePresetSelect('supersedes')}
          >
            <span className="kg-dot" style={{ background: '#f59e0b' }}></span>
            Supersessions ({graphData.stats?.supersedes ?? '0'})
          </button>

          <button
            type="button"
            className={`kg-preset-btn ${activePreset === 'contextual_differences' ? 'active-contextual' : ''}`}
            onClick={() => handlePresetSelect('contextual_differences')}
          >
            <span className="kg-dot" style={{ background: '#3b82f6' }}></span>
            Contextual Diffs
          </button>

          <button
            type="button"
            className={`kg-preset-btn ${activePreset === 'corroborations' ? 'active-corroborations' : ''}`}
            onClick={() => handlePresetSelect('corroborations')}
          >
            <span className="kg-dot" style={{ background: '#10b981' }}></span>
            Corroborations
          </button>

          <button
            type="button"
            className={`kg-preset-btn ${activePreset === 'relationships' ? 'active-relationships' : ''}`}
            onClick={() => handlePresetSelect('relationships')}
          >
            <span className="kg-dot" style={{ background: '#a855f7' }}></span>
            All Types
          </button>
        </div>

        {/* Right: Entity Switcher, Doc Switcher & Zoom Controls */}
        <div className="kg-actions-group">
          {/* Document Autocomplete Selector */}
          <div className="kg-dropdown-wrapper">
            <button
              type="button"
              className={`kg-dropdown-btn ${paramDocId ? 'active-filter' : ''}`}
              onClick={() => {
                setIsDocDropdownOpen(!isDocDropdownOpen);
                setIsEntityDropdownOpen(false);
              }}
            >
              <IconFileText style={{ width: 14, height: 14, color: '#22d3ee' }} />
              <span style={{ maxWidth: 130, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {paramDocId ? (documentsList.find((d) => d.id === paramDocId)?.filename || 'Filtered Doc') : 'All Documents'}
              </span>
              {paramDocId && (
                <span
                  role="button"
                  tabIndex={0}
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDocSelect(null);
                  }}
                  style={{ marginLeft: 4, cursor: 'pointer', color: '#f43f5e', fontWeight: 'bold' }}
                  title="Clear document filter"
                >
                  &times;
                </span>
              )}
              <IconChevronRight style={{ width: 12, height: 12, transform: 'rotate(90deg)', color: '#94a3b8' }} />
            </button>

            {isDocDropdownOpen && (
              <div className="kg-dropdown-menu" style={{ left: 0, right: 'auto' }}>
                <input
                  type="text"
                  placeholder="Filter documents..."
                  value={docSearchQuery}
                  onChange={(e) => setDocSearchQuery(e.target.value)}
                  className="kg-dropdown-search"
                  autoFocus
                />
                <button
                  type="button"
                  className={`kg-dropdown-item ${!paramDocId ? 'selected' : ''}`}
                  onClick={() => handleDocSelect(null)}
                >
                  <span>All Documents (Global)</span>
                </button>
                {documentsList
                  .filter((d) => (d.filename || '').toLowerCase().includes(docSearchQuery.toLowerCase()))
                  .map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      className={`kg-dropdown-item ${paramDocId === item.id ? 'selected' : ''}`}
                      onClick={() => handleDocSelect(item.id)}
                    >
                      <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={item.filename}>
                        {item.filename}
                      </span>
                      <span style={{ fontSize: 10, color: '#64748b', fontFamily: 'monospace', flexShrink: 0, marginLeft: 8 }}>
                        {item.document_type || 'PDF'}
                      </span>
                    </button>
                  ))}
              </div>
            )}
          </div>

          {/* Entity Autocomplete Selector */}
          <div className="kg-dropdown-wrapper">
            <button
              type="button"
              className={`kg-dropdown-btn ${paramEntity ? 'active-filter' : ''}`}
              onClick={() => {
                setIsEntityDropdownOpen(!isEntityDropdownOpen);
                setIsDocDropdownOpen(false);
              }}
            >
              <IconSearch style={{ width: 14, height: 14, color: '#818cf8' }} />
              <span style={{ maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {paramEntity || 'Switch Entity...'}
              </span>
              <IconChevronRight style={{ width: 12, height: 12, transform: 'rotate(90deg)', color: '#94a3b8' }} />
            </button>

            {isEntityDropdownOpen && (
              <div className="kg-dropdown-menu" style={{ left: 0, right: 'auto' }}>
                <input
                  type="text"
                  placeholder="Filter entities..."
                  value={entitySearchQuery}
                  onChange={(e) => setEntitySearchQuery(e.target.value)}
                  className="kg-dropdown-search"
                  autoFocus
                />
                <button
                  type="button"
                  className={`kg-dropdown-item ${!paramEntity ? 'selected' : ''}`}
                  onClick={() => handleEntitySelect(null)}
                >
                  <span>All Entities (Global)</span>
                </button>
                {entitiesList
                  .filter((e) => e.name.toLowerCase().includes(entitySearchQuery.toLowerCase()))
                  .map((item) => (
                    <button
                      key={item.name}
                      type="button"
                      className={`kg-dropdown-item ${paramEntity === item.name ? 'selected' : ''}`}
                      onClick={() => handleEntitySelect(item.name)}
                    >
                      <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {item.name}
                      </span>
                      <span style={{ fontSize: 10, color: '#818cf8', fontFamily: 'monospace', flexShrink: 0, marginLeft: 8 }}>
                        {item.facts_count} claims
                      </span>
                    </button>
                  ))}
              </div>
            )}
          </div>

          {/* Node Visibility Toggles */}
          <div className="kg-visibility-group">
            <button
              type="button"
              className={`kg-vis-btn ${nodeTypeVisibility.entity ? 'active-entity' : ''}`}
              onClick={() => setNodeTypeVisibility((v) => ({ ...v, entity: !v.entity }))}
              title="Toggle Entity Hubs"
            >
              Entities
            </button>
            <button
              type="button"
              className={`kg-vis-btn ${nodeTypeVisibility.document ? 'active-doc' : ''}`}
              onClick={() => setNodeTypeVisibility((v) => ({ ...v, document: !v.document }))}
              title="Toggle Document Nodes"
            >
              Docs
            </button>
            <button
              type="button"
              className={`kg-vis-btn ${nodeTypeVisibility.fact ? 'active-fact' : ''}`}
              onClick={() => setNodeTypeVisibility((v) => ({ ...v, fact: !v.fact }))}
              title="Toggle Fact Nodes"
            >
              Facts
            </button>
          </div>

          {/* Zoom Buttons in Toolbar */}
          <div className="kg-zoom-group">
            <button
              type="button"
              className="kg-tool-btn"
              onClick={zoomIn}
              title="Zoom In (+)"
            >
              <IconZoomIn style={{ width: 14, height: 14 }} />
            </button>
            <button
              type="button"
              className="kg-tool-btn"
              style={{ fontFamily: 'monospace', fontWeight: 700, minWidth: 42 }}
              onClick={resetZoom}
              title="Reset to 100% Zoom"
            >
              {Math.round(transform.scale * 100)}%
            </button>
            <button
              type="button"
              className="kg-tool-btn"
              onClick={zoomOut}
              title="Zoom Out (-)"
            >
              <IconZoomOut style={{ width: 14, height: 14 }} />
            </button>
            <button
              type="button"
              className="kg-tool-btn"
              onClick={() => fitToView()}
              title="Fit Entire Graph to View"
            >
              <IconMaximize style={{ width: 14, height: 14 }} />
            </button>
            <button
              type="button"
              className="kg-tool-btn"
              onClick={centerOnFocused}
              title="Center on Focal Claim"
            >
              <IconCompass style={{ width: 14, height: 14, color: '#818cf8' }} />
            </button>
          </div>
        </div>
      </div>

      {/* Dynamic Tab Context Banner */}
      {contextDescription && (
        <div className="kg-scope-banner">
          <div className="kg-scope-left">
            <div className="kg-pulse-dot"></div>
            <span className="kg-scope-label">Active Scope:</span>
            <span className="kg-scope-tag">{contextDescription}</span>
          </div>
          <div className="kg-scope-right">
            <button
              type="button"
              onClick={handleResetToGlobal}
              className="kg-banner-btn"
              title="Clear all filters and return to global view"
            >
              <IconRefreshCw style={{ width: 12, height: 12, color: '#818cf8' }} />
              <span>Reset to Global Graph</span>
            </button>
            {originTabLink && (
              <Link
                to={originTabLink.url}
                className="kg-banner-btn kg-banner-btn-origin"
              >
                <span>Back to {originTabLink.label}</span>
                <IconChevronRight style={{ width: 12, height: 12 }} />
              </Link>
            )}
          </div>
        </div>
      )}

      {/* Main Workspace Layout (Graph Canvas + Side Drawer) */}
      <div className="kg-workspace">
        {/* SVG Interactive Canvas */}
        <div
          className="kg-canvas"
          onWheel={handleWheel}
          onMouseDown={handleMouseDownCanvas}
          onMouseMove={handleMouseMoveCanvas}
          onMouseUp={handleMouseUpCanvas}
        >
          {loading && (
            <div style={{ position: 'absolute', inset: 0, background: 'rgba(8, 12, 20, 0.7)', backdropFilter: 'blur(4px)', zIndex: 30, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
                <IconRefreshCw style={{ width: 32, height: 32, color: '#818cf8', animation: 'spin 1s linear infinite' }} />
                <span style={{ fontSize: 13, fontWeight: 600, color: '#cbd5e1' }}>Resolving multi-hop graph topology...</span>
              </div>
            </div>
          )}

          {error && (
            <div style={{ position: 'absolute', top: 16, left: 16, zIndex: 30, background: 'rgba(76, 5, 25, 0.85)', border: '1px solid rgba(225, 29, 72, 0.6)', borderRadius: 12, padding: 16, maxWidth: 440, boxShadow: '0 10px 25px rgba(0,0,0,0.5)' }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                <IconAlertTriangle style={{ width: 20, height: 20, color: '#fb7185', flexShrink: 0, marginTop: 2 }} />
                <div>
                  <h4 style={{ fontSize: 12, fontWeight: 700, color: '#ffe4e6', margin: 0 }}>Could not assemble Knowledge Graph</h4>
                  <p style={{ fontSize: 12, color: '#fda4af', margin: '4px 0 0 0' }}>{error}</p>
                </div>
              </div>
            </div>
          )}

          <svg
            ref={svgRef}
            className="w-full h-full"
            style={{ width: '100%', height: '100%' }}
          >
            <defs>
              {/* Background Tech Grid */}
              <pattern id="canvas-grid" width="40" height="40" patternUnits="userSpaceOnUse">
                <circle cx="20" cy="20" r="1" fill="#334155" opacity="0.4" />
                <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#1e293b" strokeWidth="0.5" opacity="0.4" />
              </pattern>

              {/* Arrow Markers for Directed Relationships */}
              <marker id="arrow-contradicts" viewBox="0 0 10 10" refX="28" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 1 L 10 5 L 0 9 z" fill="#ef4444" />
              </marker>
              <marker id="arrow-corroborates" viewBox="0 0 10 10" refX="28" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 1 L 10 5 L 0 9 z" fill="#10b981" />
              </marker>
              <marker id="arrow-supersedes" viewBox="0 0 10 10" refX="28" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 1 L 10 5 L 0 9 z" fill="#f59e0b" />
              </marker>
              <marker id="arrow-contextual" viewBox="0 0 10 10" refX="28" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 1 L 10 5 L 0 9 z" fill="#3b82f6" />
              </marker>

              {/* Glow Filters */}
              <filter id="glow-focused" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="6" result="coloredBlur" />
                <feMerge>
                  <feMergeNode in="coloredBlur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>

            {/* Grid background rectangle */}
            <rect id="canvas-grid-bg" width="100%" height="100%" fill="url(#canvas-grid)" />

            {/* Zoomable / Pannable Workspace Container */}
            <g transform={`translate(${transform.x}, ${transform.y}) scale(${transform.scale})`}>
              {/* 1. Render Edges (Links) */}
              <g className="edges-layer">
                {visibleEdges.map((edge) => {
                  const p1 = nodePositions[edge.source];
                  const p2 = nodePositions[edge.target];
                  if (!p1 || !p2) return null;

                  const dx = p2.x - p1.x;
                  const dy = p2.y - p1.y;
                  const midX = (p1.x + p2.x) / 2;
                  const midY = (p1.y + p2.y) / 2;
                  // Slight curve for visual elegance
                  const curveOffset = Math.sin((p1.x + p2.x) * 0.01) * 25;
                  const ctrlX = midX - (dy / (Math.sqrt(dx * dx + dy * dy) || 1)) * curveOffset;
                  const ctrlY = midY + (dx / (Math.sqrt(dx * dx + dy * dy) || 1)) * curveOffset;

                  const isRel = edge.type !== 'HAS_FACT' && edge.type !== 'EXTRACTED_FROM';
                  const isSelected = selectedEdge?.id === edge.id;
                  const isDimmed =
                    hoveredNodeId && edge.source !== hoveredNodeId && edge.target !== hoveredNodeId;

                  const style = getEdgeStyle(edge);
                  const markerId =
                    edge.type === 'CONTRADICTS'
                      ? 'url(#arrow-contradicts)'
                      : edge.type === 'CORROBORATES'
                      ? 'url(#arrow-corroborates)'
                      : edge.type === 'SUPERSEDES'
                      ? 'url(#arrow-supersedes)'
                      : edge.type === 'CONTEXTUAL_DIFFERENCE'
                      ? 'url(#arrow-contextual)'
                      : undefined;

                  return (
                    <g
                      key={edge.id}
                      style={{ opacity: isDimmed ? 0.2 : 1, transition: 'opacity 0.2s ease', cursor: isRel ? 'pointer' : 'default' }}
                      onClick={(e) => {
                        e.stopPropagation();
                        if (isRel) setSelectedEdge(edge);
                      }}
                    >
                      {/* Edge Path */}
                      <path
                        d={`M ${p1.x} ${p1.y} Q ${ctrlX} ${ctrlY} ${p2.x} ${p2.y}`}
                        fill="none"
                        stroke={isSelected ? '#ffffff' : style.stroke}
                        strokeWidth={isSelected ? style.strokeWidth + 2 : style.strokeWidth}
                        strokeDasharray={style.strokeDasharray}
                        markerEnd={markerId}
                        opacity={isSelected ? 1 : 0.8}
                      />

                      {/* Relationship Badge Pill at Midpoint */}
                      {isRel && (
                        <g transform={`translate(${ctrlX}, ${ctrlY})`} style={{ cursor: 'pointer' }}>
                          <rect
                            x="-63"
                            y="-14"
                            width="126"
                            height="28"
                            rx="14"
                            fill={isSelected ? '#ffffff' : '#0a0f1d'}
                            stroke={style.stroke}
                            strokeWidth={isSelected ? '2.5' : '1.8'}
                            filter="drop-shadow(0 4px 10px rgba(0,0,0,0.5))"
                          />
                          <text
                            textAnchor="middle"
                            y="4.5"
                            fontSize="11"
                            fontWeight="800"
                            fontFamily="monospace"
                            letterSpacing="0.04em"
                            fill={isSelected ? '#0f172a' : style.stroke}
                            className="select-none pointer-events-none"
                          >
                            {edge.type.substring(0, 14)}
                          </text>
                        </g>
                      )}

                      {/* Document Grounding Page Label */}
                      {edge.type === 'EXTRACTED_FROM' && edge.page_number && (
                        <g transform={`translate(${ctrlX}, ${ctrlY})`}>
                          <rect
                            x="-30"
                            y="-11"
                            width="60"
                            height="22"
                            rx="11"
                            fill="#083344"
                            stroke="#06b6d4"
                            strokeWidth="1.5"
                            filter="drop-shadow(0 2px 6px rgba(0,0,0,0.4))"
                          />
                          <text
                            textAnchor="middle"
                            y="4"
                            fontSize="10"
                            fontWeight="800"
                            fontFamily="monospace"
                            fill="#67e8f9"
                            className="select-none pointer-events-none"
                          >
                            p. {edge.page_number}
                          </text>
                        </g>
                      )}
                    </g>
                  );
                })}
              </g>

              {/* 2. Render Nodes */}
              <g className="nodes-layer">
                {visibleNodes.map((node) => {
                  const pos = nodePositions[node.id];
                  if (!pos) return null;

                  const isSelected = selectedNode?.id === node.id;
                  const isFocused = node.is_focused;
                  const isDimmed = isNodeDimmed(node.id);

                  return (
                    <g
                      key={node.id}
                      transform={`translate(${pos.x}, ${pos.y})`}
                      style={{ opacity: isDimmed ? 0.25 : 1, transition: 'opacity 0.2s ease', cursor: 'pointer' }}
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedNode(node);
                        setSelectedEdge(null);
                      }}
                      onMouseEnter={() => setHoveredNodeId(node.id)}
                      onMouseLeave={() => setHoveredNodeId(null)}
                      onMouseDown={(e) => {
                        e.stopPropagation();
                        setDraggedNodeId(node.id);
                      }}
                    >
                      {/* Pulsing ring for focused fact claim */}
                      {isFocused && (
                        <circle
                          r="56"
                          fill="none"
                          stroke="#818cf8"
                          strokeWidth="2.5"
                          opacity="0.8"
                        />
                      )}

                      {/* NODE TYPE A: ENTITY HUB */}
                      {node.type === 'entity' && (
                        <g>
                          <circle
                            r={isSelected ? 52 : 48}
                            fill="url(#entity-grad)"
                            stroke={isSelected ? '#c7d2fe' : '#6366f1'}
                            strokeWidth={isSelected ? 3.5 : 2.5}
                            filter={isFocused ? 'url(#glow-focused)' : 'drop-shadow(0 6px 16px rgba(99,102,241,0.3))'}
                          />
                          {/* Radial gradient for entity */}
                          <defs>
                            <radialGradient id="entity-grad" cx="50%" cy="50%" r="50%">
                              <stop offset="0%" stopColor="#312e81" />
                              <stop offset="100%" stopColor="#1e1b4b" />
                            </radialGradient>
                          </defs>
                          <text
                            textAnchor="middle"
                            y="-8"
                            fontSize="13"
                            fontWeight="bold"
                            fill="#ffffff"
                            className="select-none pointer-events-none"
                          >
                            {node.label.length > 15 ? node.label.substring(0, 14) + '…' : node.label}
                          </text>
                          {/* Fact count pill */}
                          <rect
                            x="-28"
                            y="6"
                            width="56"
                            height="18"
                            rx="9"
                            fill="#4338ca"
                            stroke="#6366f1"
                            strokeWidth="1"
                          />
                          <text
                            textAnchor="middle"
                            y="19"
                            fontSize="10"
                            fontWeight="bold"
                            fontFamily="monospace"
                            fill="#e0e7ff"
                            className="select-none pointer-events-none"
                          >
                            {node.fact_count} claims
                          </text>
                        </g>
                      )}

                      {/* NODE TYPE B: DOCUMENT BADGE */}
                      {node.type === 'document' && (
                        <g>
                          <rect
                            x="-90"
                            y="-29"
                            width="180"
                            height="58"
                            rx="12"
                            fill="#042f2e"
                            stroke={isSelected ? '#5eead4' : '#0d9488'}
                            strokeWidth={isSelected ? 3 : 1.8}
                            filter="drop-shadow(0 4px 12px rgba(0,0,0,0.5))"
                          />
                          <text
                            textAnchor="middle"
                            y="-6"
                            fontSize="12.5"
                            fontWeight="bold"
                            fill="#ccfbf1"
                            className="select-none pointer-events-none"
                          >
                            📄 {node.label && node.label.length > 18 ? node.label.substring(0, 17) + '…' : (node.label || 'Document')}
                          </text>
                          <text
                            textAnchor="middle"
                            y="14"
                            fontSize="10.5"
                            fontFamily="monospace"
                            fontWeight="600"
                            fill="#5eead4"
                            className="select-none pointer-events-none"
                          >
                            {node.page_count || 1} pages &bull; {node.facts_count || 0} facts
                          </text>
                        </g>
                      )}

                      {/* NODE TYPE C: FACT CLAIM CARD */}
                      {node.type === 'fact' && (() => {
                        const role = nodeRoleMap[node.id];
                        let strokeColor = '#334155';
                        let cardBg = '#0b1120';
                        let headerBg = 'rgba(51, 65, 85, 0.4)';
                        let headerText = '#94a3b8';
                        let accentLine = '#334155';

                        if (isFocused) {
                          strokeColor = '#818cf8';
                          cardBg = '#13112c';
                          headerBg = 'rgba(99, 102, 241, 0.3)';
                          headerText = '#c7d2fe';
                          accentLine = '#6366f1';
                        } else if (isSelected) {
                          strokeColor = '#38bdf8';
                          cardBg = '#0f172a';
                          headerBg = 'rgba(56, 189, 248, 0.25)';
                          headerText = '#7dd3fc';
                          accentLine = '#38bdf8';
                        } else if (role === 'CONTRADICTS') {
                          strokeColor = '#f43f5e';
                          cardBg = '#1c0d14';
                          headerBg = 'rgba(244, 63, 94, 0.25)';
                          headerText = '#fda4af';
                          accentLine = '#f43f5e';
                        } else if (role === 'SUPERSEDES') {
                          strokeColor = '#f59e0b';
                          cardBg = '#1f160a';
                          headerBg = 'rgba(245, 158, 11, 0.25)';
                          headerText = '#fde68a';
                          accentLine = '#f59e0b';
                        } else if (role === 'CORROBORATES') {
                          strokeColor = '#10b981';
                          cardBg = '#071b14';
                          headerBg = 'rgba(16, 185, 129, 0.25)';
                          headerText = '#a7f3d0';
                          accentLine = '#10b981';
                        } else if (role === 'CONTEXTUAL_DIFFERENCE') {
                          strokeColor = '#3b82f6';
                          cardBg = '#0c1527';
                          headerBg = 'rgba(59, 130, 246, 0.25)';
                          headerText = '#93c5fd';
                          accentLine = '#3b82f6';
                        }

                        const strokeWidth = isFocused ? 3 : isSelected ? 2.5 : (role ? 2 : 1.5);

                        return (
                          <g filter="drop-shadow(0 6px 20px rgba(0,0,0,0.55))">
                            {/* Main Card Shell */}
                            <rect
                              x="-120"
                              y="-43"
                              width="240"
                              height="86"
                              rx="12"
                              fill={cardBg}
                              stroke={strokeColor}
                              strokeWidth={strokeWidth}
                            />

                            {/* Header Accent Band */}
                            <path
                              d="M -120 -31 A 12 12 0 0 1 -108 -43 L 108 -43 A 12 12 0 0 1 120 -31 L 120 -17 L -120 -17 Z"
                              fill={headerBg}
                            />
                            <line
                              x1="-120"
                              y1="-17"
                              x2="120"
                              y2="-17"
                              stroke={accentLine}
                              strokeWidth="1"
                              opacity="0.6"
                            />

                            {/* Predicate title in header band */}
                            <text
                              textAnchor="middle"
                              y="-26"
                              fontSize="11"
                              fontWeight="800"
                              fontFamily="monospace"
                              fill={headerText}
                              className="select-none pointer-events-none"
                              letterSpacing="0.04em"
                            >
                              {node.predicate && node.predicate.length > 24 ? node.predicate.substring(0, 23) + '…' : (node.predicate || 'CLAIM').toUpperCase()}
                            </text>

                            {/* Main Value Display */}
                            <text
                              textAnchor="middle"
                              y="9"
                              fontSize="16.5"
                              fontWeight="800"
                              fill="#ffffff"
                              className="select-none pointer-events-none"
                            >
                              {String(node.value || '').length > 20 ? String(node.value).substring(0, 19) + '…' : (node.value ?? 'N/A')}{' '}
                              {node.unit && (
                                <tspan fontSize="11" fill="#93c5fd" fontWeight="bold">
                                  {node.unit}
                                </tspan>
                              )}
                            </text>

                            {/* Provenance Document / Page footer */}
                            <text
                              textAnchor="middle"
                              y="29"
                              fontSize="10.5"
                              fontFamily="monospace"
                              fontWeight="600"
                              fill="#94a3b8"
                              className="select-none pointer-events-none"
                            >
                              {node.document_name ? `${node.document_name.substring(0, 14)} p.${node.page_number}` : `p. ${node.page_number}`} &bull; {Math.round((node.confidence || 0.95) * 100)}% conf
                            </text>
                          </g>
                        );
                      })()}
                    </g>
                  );
                })}
              </g>
            </g>
          </svg>

          {/* Canvas Legend & Help overlay */}
          <div className="kg-legend">
            <div className="kg-legend-title">
              <IconSparkles style={{ width: 14, height: 14, color: '#818cf8' }} />
              <span>Multi-Hop Legend</span>
            </div>
            <div className="kg-legend-grid">
              <div className="kg-legend-item">
                <span className="kg-dot" style={{ background: '#6366f1' }}></span>
                <span>Entity Hub</span>
              </div>
              <div className="kg-legend-item">
                <span style={{ width: 8, height: 8, borderRadius: 2, background: '#334155', border: '1px solid #64748b' }}></span>
                <span>Fact Claim</span>
              </div>
              <div className="kg-legend-item">
                <span style={{ width: 12, height: 2, background: '#f43f5e' }}></span>
                <span style={{ color: '#fda4af', fontWeight: 600 }}>Contradiction</span>
              </div>
              <div className="kg-legend-item">
                <span style={{ width: 12, height: 2, background: '#10b981' }}></span>
                <span style={{ color: '#a7f3d0', fontWeight: 600 }}>Corroboration</span>
              </div>
              <div className="kg-legend-item">
                <span style={{ width: 12, height: 2, background: '#f59e0b' }}></span>
                <span style={{ color: '#fde68a', fontWeight: 600 }}>Supersession</span>
              </div>
              <div className="kg-legend-item">
                <span style={{ width: 12, height: 2, background: '#06b6d4' }}></span>
                <span style={{ color: '#67e8f9', fontWeight: 600 }}>Source Page</span>
              </div>
            </div>
            <div className="kg-legend-tip">
              Scroll wheel to zoom to pointer &bull; Drag canvas or nodes
            </div>
          </div>

          {/* Floating Canvas Dock for Zoom, Fit & Layout Spacing */}
          <div className="kg-floating-dock">
            {/* Zoom Controls */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <button
                type="button"
                className="kg-dock-btn"
                onClick={zoomIn}
                title="Zoom In (+)"
              >
                <IconZoomIn style={{ width: 15, height: 15 }} />
              </button>
              <button
                type="button"
                className="kg-dock-pill"
                onClick={resetZoom}
                title="Reset to 100% Zoom"
              >
                {Math.round(transform.scale * 100)}%
              </button>
              <button
                type="button"
                className="kg-dock-btn"
                onClick={zoomOut}
                title="Zoom Out (-)"
              >
                <IconZoomOut style={{ width: 15, height: 15 }} />
              </button>
            </div>

            <div className="kg-dock-divider"></div>

            {/* Viewport Fit & Focus */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <button
                type="button"
                className="kg-dock-btn"
                onClick={() => fitToView()}
                title="Fit Entire Graph to Screen"
              >
                <IconMaximize style={{ width: 15, height: 15 }} />
              </button>
              <button
                type="button"
                className="kg-dock-btn"
                onClick={centerOnFocused}
                title="Center on Focal Claim / Pair"
              >
                <IconCompass style={{ width: 15, height: 15, color: '#818cf8' }} />
              </button>
              <button
                type="button"
                className="kg-dock-btn"
                onClick={() => reSimulateLayout(layoutSpacing)}
                title="Auto-Untangle Nodes (Re-simulate Layout)"
              >
                <IconRefreshCw style={{ width: 14, height: 14, color: '#818cf8' }} />
              </button>
            </div>

            <div className="kg-dock-divider"></div>

            {/* Node Spacing Segmented Control */}
            <div className="kg-spacing-picker">
              <span className="kg-spacing-label">Spacing:</span>
              {[
                { label: 'Compact', val: 0.85 },
                { label: 'Balanced', val: 1.15 },
                { label: 'Spacious', val: 1.5 },
                { label: 'Wide', val: 2.0 },
              ].map((sp) => (
                <button
                  key={sp.label}
                  type="button"
                  className={`kg-spacing-btn ${layoutSpacing === sp.val ? 'active' : ''}`}
                  onClick={() => handleSpacingChange(sp.val)}
                >
                  {sp.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Right-Hand Inspector Drawer */}
        <div className="kg-inspector">
          <div className="kg-inspector-header">
            <div className="kg-inspector-title">
              <IconSparkles style={{ width: 15, height: 15, color: '#818cf8' }} />
              <span>Provenance Inspector</span>
              {selectedNode && (
                <span className="kg-inspector-badge">
                  {selectedNode.type}
                </span>
              )}
              {selectedEdge && (
                <span className="kg-inspector-badge" style={{ color: '#f43f5e' }}>
                  relationship
                </span>
              )}
            </div>
            <button
              type="button"
              className="kg-inspector-close"
              onClick={() => {
                setSelectedNode(null);
                setSelectedEdge(null);
              }}
              title="Close Inspector"
            >
              <IconX style={{ width: 16, height: 16 }} />
            </button>
          </div>

          <div className="kg-inspector-body">
            {/* INSPECTOR VIEW 1: FACT CLAIM NODE */}
            {selectedNode && selectedNode.type === 'fact' && (
              <>
                <div>
                  <span className="kg-inspector-label" style={{ color: '#818cf8' }}>
                    {selectedNode.entity_name} &bull; {selectedNode.predicate}
                  </span>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginTop: 4 }}>
                    <h3 className="kg-inspector-value" style={{ fontSize: 20, margin: 0 }}>
                      {selectedNode.value}
                    </h3>
                    {selectedNode.unit && (
                      <span style={{ fontSize: 13, color: '#94a3b8' }}>{selectedNode.unit}</span>
                    )}
                  </div>
                </div>

                {/* Primary Action Button: Jump to PDF Viewer */}
                {selectedNode.document_id && (
                  <Link
                    to={`/viewer/${selectedNode.document_id}?fact_id=${selectedNode.id}`}
                    className="kg-inspector-btn kg-inspector-btn-primary"
                  >
                    <IconEye style={{ width: 16, height: 16 }} />
                    <span>Open in PDF Viewer (Page {selectedNode.page_number})</span>
                  </Link>
                )}

                {/* 4-Grid Attributes */}
                <div className="kg-inspector-grid">
                  <div className="kg-inspector-card">
                    <span className="kg-inspector-card-label">Fiscal Period</span>
                    <span className="kg-inspector-card-val">{selectedNode.fiscal_year || 'FY2024'}</span>
                  </div>
                  <div className="kg-inspector-card">
                    <span className="kg-inspector-card-label">Confidence</span>
                    <span className="kg-inspector-card-val success">
                      {((selectedNode.confidence || 0.95) * 100).toFixed(0)}% Verified
                    </span>
                  </div>
                  <div className="kg-inspector-card">
                    <span className="kg-inspector-card-label">Category</span>
                    <span className="kg-inspector-card-val" style={{ textTransform: 'capitalize' }}>
                      {selectedNode.category || 'Financial'}
                    </span>
                  </div>
                  <div className="kg-inspector-card">
                    <span className="kg-inspector-card-label">Accounting Scope</span>
                    <span className="kg-inspector-card-val">
                      {selectedNode.basis || 'GAAP'} &bull; {selectedNode.scope || 'Consol.'}
                    </span>
                  </div>
                </div>

                {/* Ground-Truth Verbatim Excerpt */}
                <div>
                  <label className="kg-inspector-label">
                    Verbatim Grounding Excerpt
                  </label>
                  <div className="kg-inspector-quote">
                    "{selectedNode.snippet || selectedNode.value}"
                  </div>
                </div>

                {/* Source Document Card */}
                <div className="kg-inspector-card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div>
                    <span className="kg-inspector-card-label">Source Document</span>
                    <span className="kg-inspector-card-val">{selectedNode.document_name}</span>
                  </div>
                  <span style={{ padding: '3px 8px', borderRadius: 6, background: '#083344', color: '#67e8f9', fontFamily: 'monospace', fontWeight: 700, fontSize: 11 }}>
                    Page {selectedNode.page_number}
                  </span>
                </div>

                {/* Relationships Involving this Fact */}
                <div>
                  <label className="kg-inspector-label">
                    Connected Relationships
                  </label>
                  <div>
                    {graphData.edges
                      .filter(
                        (e) =>
                          (e.source === selectedNode.id || e.target === selectedNode.id) &&
                          e.type !== 'HAS_FACT' &&
                          e.type !== 'EXTRACTED_FROM'
                      )
                      .map((rel) => (
                        <div
                          key={rel.id}
                          className="kg-rel-list-item"
                          onClick={() => setSelectedEdge(rel)}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                            <span
                              className={`kg-rel-badge ${
                                rel.type === 'CONTRADICTS'
                                  ? 'contradicts'
                                  : rel.type === 'SUPERSEDES'
                                  ? 'supersedes'
                                  : rel.type === 'CONTEXTUAL_DIFFERENCE'
                                  ? 'contextual'
                                  : 'corroborates'
                              }`}
                            >
                              {rel.type}
                            </span>
                            <span style={{ fontSize: 11, fontFamily: 'monospace', color: '#94a3b8' }}>
                              {Math.round((rel.confidence || 0.9) * 100)}% conf
                            </span>
                          </div>
                          <p style={{ fontSize: 12, color: '#cbd5e1', margin: 0, lineHeight: 1.4 }}>
                            {rel.explanation || 'Cross-document relationship detected between facts.'}
                          </p>
                        </div>
                      ))}
                    {graphData.edges.filter(
                      (e) =>
                        (e.source === selectedNode.id || e.target === selectedNode.id) &&
                        e.type !== 'HAS_FACT' &&
                        e.type !== 'EXTRACTED_FROM'
                    ).length === 0 && (
                      <div style={{ fontSize: 12, color: '#64748b', fontStyle: 'italic', padding: 12, borderRadius: 8, background: '#090e1a', border: '1px dashed #1e293b' }}>
                        No cross-document conflicts or supersessions detected for this single fact.
                      </div>
                    )}
                  </div>
                </div>
              </>
            )}

            {/* INSPECTOR VIEW 2: RELATIONSHIP EDGE */}
            {selectedEdge && (
              <>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span
                    className={`kg-rel-badge ${
                      selectedEdge.type === 'CONTRADICTS'
                        ? 'contradicts'
                        : selectedEdge.type === 'SUPERSEDES'
                        ? 'supersedes'
                        : selectedEdge.type === 'CONTEXTUAL_DIFFERENCE'
                        ? 'contextual'
                        : 'corroborates'
                    }`}
                    style={{ fontSize: 12, padding: '5px 12px' }}
                  >
                    {selectedEdge.type}
                  </span>
                  <span style={{ fontSize: 12, fontFamily: 'monospace', fontWeight: 700, color: '#e2e8f0' }}>
                    {Math.round((selectedEdge.confidence || 0.9) * 100)}% Confidence
                  </span>
                </div>

                {/* Primary Action Button: View Full Reasoning Trace */}
                <button
                  type="button"
                  className="kg-inspector-btn kg-inspector-btn-primary"
                  onClick={() => setActiveReasoningRel({ id: selectedEdge.rel_id || selectedEdge.id })}
                >
                  <IconSparkles style={{ width: 16, height: 16, color: '#fde68a' }} />
                  <span>View Full Reasoning Trace & Matrix</span>
                </button>

                {/* Explanation Rationale */}
                <div>
                  <label className="kg-inspector-label">
                    LLM Rationale & Conflict Rationale
                  </label>
                  <div className="kg-inspector-quote" style={{ fontStyle: 'normal' }}>
                    {selectedEdge.explanation || 'Cross-document reasoning engine identified alignment discrepancy.'}
                  </div>
                </div>

                {/* Fact A vs Fact B Comparison Cards */}
                <div>
                  <label className="kg-inspector-label">
                    Compared Grounded Claims
                  </label>
                  <div className="kg-compare-box">
                    <span className="kg-compare-title" style={{ color: '#818cf8' }}>
                      Fact Claim A
                    </span>
                    <div className="kg-compare-pred">
                      {selectedEdge.fact_a_predicate || 'Attribute'}:{' '}
                      <span style={{ color: '#34d399', fontWeight: 800 }}>{selectedEdge.fact_a_value}</span>
                    </div>
                    <div className="kg-compare-doc">
                      Doc: {selectedEdge.fact_a_doc || 'Source A'}
                    </div>
                  </div>

                  <div className="kg-compare-box">
                    <span className="kg-compare-title" style={{ color: '#c084fc' }}>
                      Fact Claim B
                    </span>
                    <div className="kg-compare-pred">
                      {selectedEdge.fact_b_predicate || 'Attribute'}:{' '}
                      <span style={{ color: '#fb7185', fontWeight: 800 }}>{selectedEdge.fact_b_value}</span>
                    </div>
                    <div className="kg-compare-doc">
                      Doc: {selectedEdge.fact_b_doc || 'Source B'}
                    </div>
                  </div>
                </div>
              </>
            )}

            {/* INSPECTOR VIEW 3: ENTITY HUB NODE */}
            {selectedNode && selectedNode.type === 'entity' && (
              <>
                <div>
                  <span className="kg-inspector-label" style={{ color: '#818cf8' }}>
                    Entity Hub
                  </span>
                  <h3 className="kg-inspector-value" style={{ fontSize: 22, margin: '4px 0 0 0' }}>
                    {selectedNode.label}
                  </h3>
                </div>

                <div className="kg-inspector-grid">
                  <div className="kg-inspector-card">
                    <span className="kg-inspector-card-label">Grounded Claims</span>
                    <span className="kg-inspector-card-val" style={{ fontSize: 18 }}>
                      {selectedNode.fact_count}
                    </span>
                  </div>
                  <div className="kg-inspector-card">
                    <span className="kg-inspector-card-label">Contradictions</span>
                    <span className="kg-inspector-card-val danger" style={{ fontSize: 18 }}>
                      {selectedNode.contradiction_count}
                    </span>
                  </div>
                </div>

                <div>
                  <label className="kg-inspector-label">
                    Claims For This Entity
                  </label>
                  <div style={{ maxHeight: 320, overflowY: 'auto' }}>
                    {graphData.nodes
                      .filter((n) => n.type === 'fact' && n.entity_name === selectedNode.label)
                      .map((f) => (
                        <div
                          key={f.id}
                          className="kg-rel-list-item"
                          onClick={() => setSelectedNode(f)}
                        >
                          <div style={{ fontSize: 12.5, fontWeight: 700, color: '#ffffff' }}>
                            {f.predicate}: <span style={{ color: '#34d399' }}>{f.value}</span>
                          </div>
                          <div style={{ fontSize: 11, color: '#94a3b8', fontFamily: 'monospace', marginTop: 4, display: 'flex', justifyContent: 'space-between' }}>
                            <span>{f.document_name}</span>
                            <span>p. {f.page_number}</span>
                          </div>
                        </div>
                      ))}
                  </div>
                </div>
              </>
            )}

            {/* INSPECTOR VIEW 4: DOCUMENT NODE */}
            {selectedNode && selectedNode.type === 'document' && (
              <>
                <div>
                  <span className="kg-inspector-label" style={{ color: '#22d3ee' }}>
                    Source Document
                  </span>
                  <h3 className="kg-inspector-value" style={{ fontSize: 18, margin: '4px 0 0 0' }}>
                    {selectedNode.label}
                  </h3>
                </div>

                <Link
                  to={`/viewer/${selectedNode.document_id}`}
                  className="kg-inspector-btn kg-inspector-btn-teal"
                >
                  <IconEye style={{ width: 16, height: 16 }} />
                  <span>Open Entire PDF in Viewer</span>
                </Link>

                <div className="kg-inspector-card" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5 }}>
                    <span style={{ color: '#94a3b8' }}>Total Pages:</span>
                    <span style={{ color: '#ffffff', fontFamily: 'monospace', fontWeight: 700 }}>
                      {selectedNode.page_count}
                    </span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5 }}>
                    <span style={{ color: '#94a3b8' }}>Extracted Claims in Graph:</span>
                    <span style={{ color: '#22d3ee', fontFamily: 'monospace', fontWeight: 700 }}>
                      {selectedNode.facts_count}
                    </span>
                  </div>
                  {selectedNode.upload_date && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5 }}>
                      <span style={{ color: '#94a3b8' }}>Ingestion Date:</span>
                      <span style={{ color: '#cbd5e1', fontFamily: 'monospace', fontSize: 11 }}>
                        {new Date(selectedNode.upload_date).toLocaleDateString()}
                      </span>
                    </div>
                  )}
                </div>
              </>
            )}

            {/* DEFAULT EMPTY STATE FOR INSPECTOR */}
            {!selectedNode && !selectedEdge && (
              <div className="kg-empty-state">
                <IconCompass style={{ width: 44, height: 44, color: '#475569' }} />
                <h4 style={{ fontSize: 14, fontWeight: 700, color: '#cbd5e1', margin: 0 }}>
                  Select any Node or Link
                </h4>
                <p style={{ fontSize: 12, color: '#64748b', lineHeight: 1.6, margin: 0 }}>
                  Click on any Fact node, Entity hub, Document, or colored Relationship line to inspect character-exact provenance and trigger reasoning audits.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Reasoning Trace Modal (4-Tab Provenance & Dimensional Matrix) */}
      {activeReasoningRel && (
        <ReasoningTraceModal
          relationship={activeReasoningRel}
          onClose={() => setActiveReasoningRel(null)}
        />
      )}
    </div>
  );
}
