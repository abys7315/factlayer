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
          initX = centerX - 180 * spacingMult;
          initY = centerY;
        } else if (node.id === relTargetId) {
          initX = centerX + 180 * spacingMult;
          initY = centerY;
        } else if (isFocused) {
          initX = centerX;
          initY = centerY;
        } else {
          const baseRadius = 260 + ringIndex * 160;
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

      // Node half-extents for bounding box collision
      const getNodeExtents = (id) => {
        const n = nodes.find((item) => item.id === id);
        if (!n) return { hw: 108, hh: 40 };
        if (n.type === 'fact') return { hw: 110, hh: 42 }; // 196x64 + buffer
        if (n.type === 'document') return { hw: 80, hh: 32 }; // 136x46 + buffer
        return { hw: 55, hh: 55 }; // entity radius 42 + buffer
      };

      const nodeIds = nodes.map((n) => n.id);
      const kRepel = Math.max(220000, nodes.length * 7000) * spacingMult;
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
            const targetDist = (isCrossRel ? 340 : 270) * spacingMult;
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
    <div className="knowledge-graph-page flex flex-col h-[calc(100vh-4.5rem)] bg-slate-950 text-slate-100 overflow-hidden font-sans">
      {/* Top Controls Toolbar */}
      <div className="graph-toolbar bg-slate-900/90 border-b border-slate-800/80 px-4 py-2.5 flex flex-wrap items-center justify-between gap-3 z-20 backdrop-blur-md">
        {/* Left: Brand & Scope */}
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-indigo-600/20 border border-indigo-500/40 flex items-center justify-center text-indigo-400 shadow-sm">
            <IconNetwork className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-sm font-bold tracking-tight text-white m-0">Knowledge Graph Explorer</h1>
              {graphData.focused_entity && (
                <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                  {graphData.focused_entity}
                </span>
              )}
            </div>
            <p className="text-[11px] text-slate-400 m-0">
              {graphData.stats?.fact_count || 0} Grounded Claims &bull; {graphData.stats?.total_relationships || 0} Cross-Document Relationships
            </p>
          </div>
        </div>

        {/* Center: Presets & Quick Filter Tabs */}
        <div className="flex flex-wrap items-center gap-1.5 bg-slate-800/80 p-1 rounded-lg border border-slate-700/60 text-xs">
          <button
            type="button"
            className={`px-2.5 py-1 rounded-md font-medium transition-all ${
              activePreset === 'all'
                ? 'bg-slate-700 text-white shadow-sm'
                : 'text-slate-300 hover:text-white hover:bg-slate-700/50'
            }`}
            onClick={() => handlePresetSelect('all')}
          >
            All
          </button>

          {paramFactId && (
            <button
              type="button"
              className={`px-2.5 py-1 rounded-md font-medium transition-all ${
                activePreset === 'focus'
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'text-slate-300 hover:text-white hover:bg-slate-700/50'
              }`}
              onClick={() => handlePresetSelect('focus')}
            >
              Focal Subgraph
            </button>
          )}

          <button
            type="button"
            className={`px-2.5 py-1 rounded-md font-medium transition-all flex items-center gap-1.5 ${
              activePreset === 'contradictions'
                ? 'bg-rose-600 text-white shadow-sm'
                : 'text-slate-300 hover:text-white hover:bg-slate-700/50'
            }`}
            onClick={() => handlePresetSelect('contradictions')}
          >
            <span className="w-2 h-2 rounded-full bg-rose-400"></span>
            Contradictions ({graphData.stats?.contradictions ?? '0'})
          </button>

          <button
            type="button"
            className={`px-2.5 py-1 rounded-md font-medium transition-all flex items-center gap-1.5 ${
              activePreset === 'supersedes'
                ? 'bg-amber-600 text-white shadow-sm'
                : 'text-slate-300 hover:text-white hover:bg-slate-700/50'
            }`}
            onClick={() => handlePresetSelect('supersedes')}
          >
            <span className="w-2 h-2 rounded-full bg-amber-400"></span>
            Supersessions ({graphData.stats?.supersedes ?? '0'})
          </button>

          <button
            type="button"
            className={`px-2.5 py-1 rounded-md font-medium transition-all flex items-center gap-1.5 ${
              activePreset === 'contextual_differences'
                ? 'bg-blue-600 text-white shadow-sm'
                : 'text-slate-300 hover:text-white hover:bg-slate-700/50'
            }`}
            onClick={() => handlePresetSelect('contextual_differences')}
          >
            <span className="w-2 h-2 rounded-full bg-blue-400"></span>
            Contextual Diffs
          </button>

          <button
            type="button"
            className={`px-2.5 py-1 rounded-md font-medium transition-all flex items-center gap-1.5 ${
              activePreset === 'corroborations'
                ? 'bg-emerald-600 text-white shadow-sm'
                : 'text-slate-300 hover:text-white hover:bg-slate-700/50'
            }`}
            onClick={() => handlePresetSelect('corroborations')}
          >
            <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
            Corroborations
          </button>

          <button
            type="button"
            className={`px-2.5 py-1 rounded-md font-medium transition-all flex items-center gap-1.5 ${
              activePreset === 'relationships'
                ? 'bg-purple-600 text-white shadow-sm'
                : 'text-slate-300 hover:text-white hover:bg-slate-700/50'
            }`}
            onClick={() => handlePresetSelect('relationships')}
          >
            <span className="w-2 h-2 rounded-full bg-purple-400"></span>
            All Types
          </button>
        </div>

        {/* Right: Entity Switcher, Doc Switcher & Zoom Controls */}
        <div className="flex items-center gap-2">
          {/* Document Autocomplete Selector */}
          <div className="relative">
            <button
              type="button"
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs transition-colors ${
                paramDocId ? 'bg-indigo-950/80 border-indigo-500/60 text-indigo-200' : 'bg-slate-800 border-slate-700 text-slate-200 hover:border-indigo-500/60'
              }`}
              onClick={() => {
                setIsDocDropdownOpen(!isDocDropdownOpen);
                setIsEntityDropdownOpen(false);
              }}
            >
              <IconFileText className="w-3.5 h-3.5 text-cyan-400" />
              <span className="max-w-[120px] truncate">
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
                  className="hover:text-rose-400 ml-0.5 text-slate-400 font-bold"
                  title="Clear document filter"
                >
                  &times;
                </span>
              )}
              <IconChevronRight className="w-3 h-3 text-slate-400 transform rotate-90" />
            </button>

            {isDocDropdownOpen && (
              <div className="absolute right-0 mt-1 w-72 max-h-72 bg-slate-900 border border-slate-700 rounded-xl shadow-2xl p-2 z-50 overflow-y-auto">
                <input
                  type="text"
                  placeholder="Filter documents..."
                  value={docSearchQuery}
                  onChange={(e) => setDocSearchQuery(e.target.value)}
                  className="w-full px-2 py-1.5 mb-2 rounded bg-slate-800 border border-slate-700 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                  autoFocus
                />
                <button
                  type="button"
                  className="w-full text-left px-2 py-1.5 rounded hover:bg-indigo-950/60 hover:text-indigo-300 text-xs text-slate-300 transition-colors mb-1 font-semibold"
                  onClick={() => handleDocSelect(null)}
                >
                  All Documents (Global)
                </button>
                <div className="space-y-1">
                  {documentsList
                    .filter((d) => (d.filename || '').toLowerCase().includes(docSearchQuery.toLowerCase()))
                    .map((item) => (
                      <button
                        key={item.id}
                        type="button"
                        className={`w-full text-left px-2 py-1.5 rounded hover:bg-indigo-950/60 hover:text-indigo-300 text-xs flex items-center justify-between transition-colors ${
                          paramDocId === item.id ? 'bg-indigo-900/40 text-indigo-200 font-semibold' : 'text-slate-300'
                        }`}
                        onClick={() => handleDocSelect(item.id)}
                      >
                        <span className="truncate max-w-[190px]" title={item.filename}>{item.filename}</span>
                        <span className="text-[10px] text-slate-500 font-mono">{item.document_type || 'PDF'}</span>
                      </button>
                    ))}
                </div>
              </div>
            )}
          </div>

          {/* Entity Autocomplete Selector */}
          <div className="relative">
            <button
              type="button"
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-800 border border-slate-700 text-xs text-slate-200 hover:border-indigo-500/60 transition-colors"
              onClick={() => {
                setIsEntityDropdownOpen(!isEntityDropdownOpen);
                setIsDocDropdownOpen(false);
              }}
            >
              <IconSearch className="w-3.5 h-3.5 text-indigo-400" />
              <span className="max-w-[110px] truncate">{paramEntity || 'Switch Entity...'}</span>
              <IconChevronRight className="w-3 h-3 text-slate-400 transform rotate-90" />
            </button>

            {isEntityDropdownOpen && (
              <div className="absolute right-0 mt-1 w-64 max-h-72 bg-slate-900 border border-slate-700 rounded-xl shadow-2xl p-2 z-50 overflow-y-auto">
                <input
                  type="text"
                  placeholder="Filter entities..."
                  value={entitySearchQuery}
                  onChange={(e) => setEntitySearchQuery(e.target.value)}
                  className="w-full px-2 py-1.5 mb-2 rounded bg-slate-800 border border-slate-700 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                  autoFocus
                />
                <button
                  type="button"
                  className="w-full text-left px-2 py-1.5 rounded hover:bg-indigo-950/60 hover:text-indigo-300 text-xs text-slate-300 transition-colors mb-1 font-semibold"
                  onClick={() => handleEntitySelect(null)}
                >
                  All Entities (Global)
                </button>
                <div className="space-y-1">
                  {entitiesList
                    .filter((e) => e.name.toLowerCase().includes(entitySearchQuery.toLowerCase()))
                    .map((item) => (
                      <button
                        key={item.name}
                        type="button"
                        className="w-full text-left px-2 py-1.5 rounded hover:bg-indigo-950/60 hover:text-indigo-300 text-xs flex items-center justify-between text-slate-300 transition-colors"
                        onClick={() => handleEntitySelect(item.name)}
                      >
                        <span className="truncate font-medium">{item.name}</span>
                        <div className="flex items-center gap-1 text-[10px]">
                          <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">{item.facts_count}f</span>
                          {item.contradictions_count > 0 && (
                            <span className="px-1 py-0.5 rounded bg-rose-950/70 text-rose-300 font-bold">
                              {item.contradictions_count}c
                            </span>
                          )}
                        </div>
                      </button>
                    ))}
                </div>
              </div>
            )}
          </div>

          {/* Node Visibility Toggles */}
          <div className="flex items-center gap-1 bg-slate-800/80 p-1 rounded-lg border border-slate-700/60 text-[11px]">
            <button
              type="button"
              className={`px-2 py-0.5 rounded transition-all ${
                nodeTypeVisibility.entity ? 'bg-indigo-900/60 text-indigo-300 font-semibold' : 'text-slate-500'
              }`}
              onClick={() => setNodeTypeVisibility((v) => ({ ...v, entity: !v.entity }))}
              title="Toggle Entity Hubs"
            >
              Entities
            </button>
            <button
              type="button"
              className={`px-2 py-0.5 rounded transition-all ${
                nodeTypeVisibility.document ? 'bg-cyan-900/60 text-cyan-300 font-semibold' : 'text-slate-500'
              }`}
              onClick={() => setNodeTypeVisibility((v) => ({ ...v, document: !v.document }))}
              title="Toggle Document Nodes"
            >
              Docs
            </button>
            <button
              type="button"
              className={`px-2 py-0.5 rounded transition-all ${
                nodeTypeVisibility.fact ? 'bg-emerald-900/60 text-emerald-300 font-semibold' : 'text-slate-500'
              }`}
              onClick={() => setNodeTypeVisibility((v) => ({ ...v, fact: !v.fact }))}
              title="Toggle Fact Nodes"
            >
              Facts
            </button>
          </div>

          {/* Zoom Buttons in Toolbar */}
          <div className="flex items-center gap-1 bg-slate-800/80 p-1 rounded-lg border border-slate-700/60">
            <button
              type="button"
              className="p-1 rounded hover:bg-slate-700 text-slate-300 hover:text-white transition-colors"
              onClick={zoomIn}
              title="Zoom In (+)"
            >
              <IconZoomIn className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              className="px-1.5 py-0.5 rounded hover:bg-slate-700 text-[11px] font-mono font-bold text-slate-300 hover:text-white transition-colors"
              onClick={resetZoom}
              title="Reset to 100% Zoom"
            >
              {Math.round(transform.scale * 100)}%
            </button>
            <button
              type="button"
              className="p-1 rounded hover:bg-slate-700 text-slate-300 hover:text-white transition-colors"
              onClick={zoomOut}
              title="Zoom Out (-)"
            >
              <IconZoomOut className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              className="p-1 rounded hover:bg-slate-700 text-slate-300 hover:text-white transition-colors"
              onClick={() => fitToView()}
              title="Fit Entire Graph to View"
            >
              <IconMaximize className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              className="p-1 rounded hover:bg-slate-700 text-slate-300 hover:text-white transition-colors"
              onClick={centerOnFocused}
              title="Center on Focal Claim"
            >
              <IconCompass className="w-3.5 h-3.5 text-indigo-400" />
            </button>
          </div>
        </div>
      </div>

      {/* Dynamic Tab Context Banner */}
      {contextDescription && (
        <div className="bg-indigo-950/90 border-b border-indigo-500/30 px-4 py-2 flex flex-wrap items-center justify-between gap-2 text-xs backdrop-blur-sm z-10 animate-fade-in shadow-inner">
          <div className="flex items-center gap-2.5">
            <span className="w-2.5 h-2.5 rounded-full bg-indigo-400 animate-pulse"></span>
            <span className="text-slate-300 font-semibold uppercase tracking-wider text-[11px]">
              Active Scope:
            </span>
            <span className="px-2 py-0.5 rounded bg-indigo-900/80 border border-indigo-500/40 text-indigo-200 font-medium text-xs">
              {contextDescription}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleResetToGlobal}
              className="px-2.5 py-1 rounded bg-slate-800/90 hover:bg-slate-700 text-slate-200 hover:text-white transition-colors text-xs flex items-center gap-1.5 border border-slate-700"
              title="Clear all tab presets, document filters, and return to the complete global knowledge graph"
            >
              <IconRefreshCw className="w-3 h-3 text-indigo-400" />
              <span>Reset to Global Graph</span>
            </button>
            {originTabLink && (
              <Link
                to={originTabLink.url}
                className="px-2.5 py-1 rounded bg-indigo-900/60 hover:bg-indigo-900 text-indigo-200 transition-colors text-xs flex items-center gap-1 border border-indigo-700/50"
              >
                <span>Back to {originTabLink.label}</span>
                <IconChevronRight className="w-3 h-3" />
              </Link>
            )}
          </div>
        </div>
      )}

      {/* Main Workspace Layout (Graph Canvas + Side Drawer) */}
      <div className="relative flex-1 flex overflow-hidden">
        {/* SVG Interactive Canvas */}
        <div
          className="relative flex-1 bg-[#0b0f19] cursor-grab active:cursor-grabbing overflow-hidden select-none"
          onWheel={handleWheel}
          onMouseDown={handleMouseDownCanvas}
          onMouseMove={handleMouseMoveCanvas}
          onMouseUp={handleMouseUpCanvas}
        >
          {loading && (
            <div className="absolute inset-0 bg-slate-950/60 backdrop-blur-sm z-30 flex items-center justify-center">
              <div className="flex flex-col items-center gap-3">
                <IconRefreshCw className="w-8 h-8 text-indigo-400 animate-spin" />
                <span className="text-sm font-medium text-slate-300">Resolving multi-hop graph topology...</span>
              </div>
            </div>
          )}

          {error && (
            <div className="absolute top-4 left-4 z-30 bg-rose-950/80 border border-rose-800/80 rounded-xl p-4 max-w-md shadow-xl">
              <div className="flex items-start gap-2.5">
                <IconAlertTriangle className="w-5 h-5 text-rose-400 flex-shrink-0 mt-0.5" />
                <div>
                  <h4 className="text-xs font-bold text-rose-200">Could not assemble Knowledge Graph</h4>
                  <p className="text-xs text-rose-300/90 mt-1">{error}</p>
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
                      className={`edge-group transition-opacity duration-200 ${
                        isDimmed ? 'opacity-20' : 'opacity-100'
                      }`}
                      onClick={(e) => {
                        e.stopPropagation();
                        if (isRel) setSelectedEdge(edge);
                      }}
                      style={{ cursor: isRel ? 'pointer' : 'default' }}
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
                        <g transform={`translate(${ctrlX}, ${ctrlY})`} className="cursor-pointer">
                          <rect
                            x="-52"
                            y="-11"
                            width="104"
                            height="22"
                            rx="11"
                            fill={isSelected ? '#ffffff' : '#0f172a'}
                            stroke={style.stroke}
                            strokeWidth={isSelected ? '2' : '1.5'}
                            className="shadow-md"
                          />
                          <text
                            textAnchor="middle"
                            y="4"
                            fontSize="9"
                            fontWeight="bold"
                            fontFamily="monospace"
                            fill={isSelected ? '#0f172a' : style.stroke}
                            className="select-none"
                          >
                            {edge.type.substring(0, 12)}
                          </text>
                        </g>
                      )}

                      {/* Document Grounding Page Label */}
                      {edge.type === 'EXTRACTED_FROM' && edge.page_number && (
                        <g transform={`translate(${ctrlX}, ${ctrlY})`}>
                          <rect
                            x="-24"
                            y="-9"
                            width="48"
                            height="18"
                            rx="9"
                            fill="#083344"
                            stroke="#06b6d4"
                            strokeWidth="1"
                            opacity="0.85"
                          />
                          <text
                            textAnchor="middle"
                            y="3"
                            fontSize="8"
                            fontWeight="bold"
                            fontFamily="monospace"
                            fill="#67e8f9"
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
                      className={`node-group cursor-pointer transition-opacity duration-200 ${
                        isDimmed ? 'opacity-25' : 'opacity-100'
                      }`}
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
                          r="46"
                          fill="none"
                          stroke="#6366f1"
                          strokeWidth="2.5"
                          className="animate-ping"
                          opacity="0.75"
                        />
                      )}

                      {/* NODE TYPE A: ENTITY HUB */}
                      {node.type === 'entity' && (
                        <g>
                          <circle
                            r={isSelected ? 42 : 38}
                            fill="url(#entity-grad)"
                            stroke={isSelected ? '#a5b4fc' : '#6366f1'}
                            strokeWidth={isSelected ? 3.5 : 2.5}
                            className="shadow-xl"
                            filter={isFocused ? 'url(#glow-focused)' : undefined}
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
                            y="-6"
                            fontSize="11"
                            fontWeight="bold"
                            fill="#e0e7ff"
                            className="select-none pointer-events-none"
                          >
                            {node.label.length > 14 ? node.label.substring(0, 13) + '…' : node.label}
                          </text>
                          {/* Fact count pill */}
                          <rect
                            x="-22"
                            y="4"
                            width="44"
                            height="14"
                            rx="7"
                            fill="#4338ca"
                            opacity="0.9"
                          />
                          <text
                            textAnchor="middle"
                            y="14"
                            fontSize="8"
                            fontWeight="bold"
                            fontFamily="monospace"
                            fill="#c7d2fe"
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
                            x="-70"
                            y="-24"
                            width="140"
                            height="48"
                            rx="10"
                            fill="#042f2e"
                            stroke={isSelected ? '#5eead4' : '#0d9488'}
                            strokeWidth={isSelected ? 2.5 : 1.5}
                            className="shadow-lg"
                          />
                          <text
                            textAnchor="middle"
                            y="-5"
                            fontSize="10"
                            fontWeight="bold"
                            fill="#ccfbf1"
                            className="select-none pointer-events-none"
                          >
                            📄 {node.label && node.label.length > 16 ? node.label.substring(0, 15) + '…' : (node.label || 'Document')}
                          </text>
                          <text
                            textAnchor="middle"
                            y="13"
                            fontSize="8.5"
                            fontFamily="monospace"
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
                        let fillColor = '#0f172a';

                        if (isFocused) {
                          strokeColor = '#818cf8';
                          fillColor = '#1e1b4b';
                        } else if (isSelected) {
                          strokeColor = '#38bdf8';
                          fillColor = '#1e293b';
                        } else if (role === 'CONTRADICTS') {
                          strokeColor = '#f43f5e';
                          fillColor = '#170b10';
                        } else if (role === 'SUPERSEDES') {
                          strokeColor = '#f59e0b';
                          fillColor = '#181208';
                        } else if (role === 'CORROBORATES') {
                          strokeColor = '#10b981';
                          fillColor = '#061712';
                        } else if (role === 'CONTEXTUAL_DIFFERENCE') {
                          strokeColor = '#3b82f6';
                          fillColor = '#091322';
                        }

                        const strokeWidth = isFocused ? 2.8 : isSelected ? 2.2 : (role ? 1.8 : 1.2);

                        return (
                          <g>
                            <rect
                              x="-98"
                              y="-32"
                              width="196"
                              height="64"
                              rx="10"
                              fill={fillColor}
                              stroke={strokeColor}
                              strokeWidth={strokeWidth}
                              className="shadow-xl"
                            />

                            {/* Predicate title */}
                            <text
                              textAnchor="middle"
                              y="-15"
                              fontSize="9.5"
                              fontWeight="bold"
                              fontFamily="monospace"
                              fill={isFocused ? '#c7d2fe' : role === 'CONTRADICTS' ? '#fda4af' : role === 'SUPERSEDES' ? '#fde68a' : role === 'CORROBORATES' ? '#a7f3d0' : '#94a3b8'}
                              className="select-none pointer-events-none uppercase tracking-wider"
                            >
                              {node.predicate && node.predicate.length > 22 ? node.predicate.substring(0, 21) + '…' : (node.predicate || 'CLAIM')}
                            </text>

                            {/* Value display */}
                            <text
                              textAnchor="middle"
                              y="5"
                              fontSize="12.5"
                              fontWeight="bold"
                              fill="#ffffff"
                              className="select-none pointer-events-none"
                            >
                              {String(node.value || '').length > 20 ? String(node.value).substring(0, 19) + '…' : (node.value ?? 'N/A')}{' '}
                              {node.unit && (
                                <tspan fontSize="8.5" fill="#a5b4fc" fontWeight="normal">
                                  {node.unit}
                                </tspan>
                              )}
                            </text>

                            {/* Provenance Document / Page pill */}
                            <text
                              textAnchor="middle"
                              y="21"
                              fontSize="8.5"
                              fontFamily="monospace"
                              fill="#64748b"
                              className="select-none pointer-events-none"
                            >
                              {node.document_name ? `${node.document_name.substring(0, 12)} p.${node.page_number}` : `p. ${node.page_number}`} &bull; {Math.round((node.confidence || 0.95) * 100)}%
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
          <div className="absolute bottom-4 left-4 bg-slate-900/90 backdrop-blur-md border border-slate-800 rounded-xl p-3 text-[11px] space-y-1.5 shadow-xl max-w-xs pointer-events-none z-20">
            <div className="font-bold text-slate-200 text-xs flex items-center gap-1.5">
              <IconSparkles className="w-3.5 h-3.5 text-indigo-400" />
              <span>Multi-Hop Legend</span>
            </div>
            <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-slate-400">
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-indigo-500"></span>
                <span>Entity Hub</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-sm bg-slate-700 border border-slate-500"></span>
                <span>Fact Claim</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-0.5 bg-rose-500"></span>
                <span className="text-rose-400 font-medium">Contradiction</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-0.5 bg-emerald-500"></span>
                <span className="text-emerald-400 font-medium">Corroboration</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-0.5 bg-amber-500"></span>
                <span className="text-amber-400 font-medium">Supersession</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-0.5 bg-cyan-500 border-t border-dashed"></span>
                <span className="text-cyan-400 font-medium">Source Page</span>
              </div>
            </div>
            <div className="text-[10px] text-slate-500 pt-1 border-t border-slate-800">
              Scroll wheel to zoom to pointer &bull; Drag canvas or nodes
            </div>
          </div>

          {/* Floating Canvas Dock for Zoom, Fit & Layout Spacing */}
          <div className="absolute bottom-4 right-4 z-20 flex flex-wrap items-center gap-2 bg-slate-900/90 backdrop-blur-md border border-slate-700/80 p-1.5 rounded-xl shadow-2xl">
            {/* Zoom Controls */}
            <div className="flex items-center gap-0.5">
              <button
                type="button"
                className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-300 hover:text-white transition-colors"
                onClick={zoomIn}
                title="Zoom In (+)"
              >
                <IconZoomIn className="w-4 h-4" />
              </button>
              <button
                type="button"
                className="px-2 py-1 rounded-lg hover:bg-slate-800 text-[11px] font-mono font-bold text-slate-300 hover:text-white transition-colors"
                onClick={resetZoom}
                title="Reset to 100% Zoom"
              >
                {Math.round(transform.scale * 100)}%
              </button>
              <button
                type="button"
                className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-300 hover:text-white transition-colors"
                onClick={zoomOut}
                title="Zoom Out (-)"
              >
                <IconZoomOut className="w-4 h-4" />
              </button>
            </div>

            <div className="w-[1px] h-4 bg-slate-700/80"></div>

            {/* Viewport Fit & Focus */}
            <div className="flex items-center gap-0.5">
              <button
                type="button"
                className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-300 hover:text-indigo-300 transition-colors"
                onClick={() => fitToView()}
                title="Fit Entire Graph to Screen"
              >
                <IconMaximize className="w-4 h-4" />
              </button>
              <button
                type="button"
                className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-300 hover:text-indigo-300 transition-colors"
                onClick={centerOnFocused}
                title="Center on Focal Claim / Pair"
              >
                <IconCompass className="w-4 h-4 text-indigo-400" />
              </button>
              <button
                type="button"
                className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-300 hover:text-indigo-300 transition-colors"
                onClick={() => reSimulateLayout(layoutSpacing)}
                title="Auto-Untangle Nodes (Re-simulate Layout)"
              >
                <IconRefreshCw className="w-3.5 h-3.5 text-indigo-400" />
              </button>
            </div>

            <div className="w-[1px] h-4 bg-slate-700/80"></div>

            {/* Node Spacing Segmented Control */}
            <div className="flex items-center gap-1 bg-slate-800/80 p-0.5 rounded-lg border border-slate-700/60 text-[10px]">
              <span className="px-1.5 text-slate-400 font-semibold uppercase tracking-wider">Spacing:</span>
              {[
                { label: 'Compact', val: 0.85 },
                { label: 'Balanced', val: 1.15 },
                { label: 'Spacious', val: 1.5 },
                { label: 'Wide', val: 2.0 },
              ].map((sp) => (
                <button
                  key={sp.label}
                  type="button"
                  className={`px-2 py-0.5 rounded transition-all font-medium ${
                    layoutSpacing === sp.val
                      ? 'bg-indigo-600 text-white shadow-sm font-semibold'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700/60'
                  }`}
                  onClick={() => handleSpacingChange(sp.val)}
                >
                  {sp.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Right-Hand Inspector Drawer */}
        <div className="w-96 bg-slate-900 border-l border-slate-800 flex flex-col z-20 shadow-2xl overflow-hidden">
          <div className="p-3.5 border-b border-slate-800 flex items-center justify-between bg-slate-950/40">
            <div className="flex items-center gap-2">
              <span className="font-bold text-xs text-white uppercase tracking-wider">Provenance Inspector</span>
              {selectedNode && (
                <span className="px-1.5 py-0.5 rounded text-[10px] uppercase font-mono font-bold bg-slate-800 text-indigo-400">
                  {selectedNode.type}
                </span>
              )}
              {selectedEdge && (
                <span className="px-1.5 py-0.5 rounded text-[10px] uppercase font-mono font-bold bg-slate-800 text-rose-400">
                  relationship
                </span>
              )}
            </div>
            <button
              type="button"
              className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-white"
              onClick={() => {
                setSelectedNode(null);
                setSelectedEdge(null);
              }}
            >
              <IconX className="w-4 h-4" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {/* INSPECTOR VIEW 1: FACT CLAIM NODE */}
            {selectedNode && selectedNode.type === 'fact' && (
              <div className="space-y-4">
                <div>
                  <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-indigo-400">
                    {selectedNode.entity_name} &bull; {selectedNode.predicate}
                  </span>
                  <h3 className="text-lg font-bold text-white mt-0.5 flex items-baseline gap-1.5">
                    <span>{selectedNode.value}</span>
                    {selectedNode.unit && (
                      <span className="text-xs font-normal text-slate-400">{selectedNode.unit}</span>
                    )}
                  </h3>
                </div>

                {/* Primary Action Button: Jump to PDF Viewer */}
                {selectedNode.document_id && (
                  <Link
                    to={`/viewer/${selectedNode.document_id}?fact_id=${selectedNode.id}`}
                    className="w-full btn btn-primary btn-sm flex items-center justify-center gap-2 py-2 text-xs font-semibold shadow-md"
                  >
                    <IconEye className="w-4 h-4" />
                    <span>Open in PDF Viewer (Page {selectedNode.page_number})</span>
                  </Link>
                )}

                {/* 6-Grid Attributes */}
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="p-2 rounded-lg bg-slate-950/70 border border-slate-800">
                    <span className="text-[10px] font-mono text-slate-500 uppercase block">Fiscal Period</span>
                    <span className="font-semibold text-slate-200">{selectedNode.fiscal_year || 'FY2024'}</span>
                  </div>
                  <div className="p-2 rounded-lg bg-slate-950/70 border border-slate-800">
                    <span className="text-[10px] font-mono text-slate-500 uppercase block">Confidence</span>
                    <span className="font-semibold text-emerald-400">
                      {((selectedNode.confidence || 0.95) * 100).toFixed(0)}% Verified
                    </span>
                  </div>
                  <div className="p-2 rounded-lg bg-slate-950/70 border border-slate-800">
                    <span className="text-[10px] font-mono text-slate-500 uppercase block">Category</span>
                    <span className="font-semibold text-slate-200 capitalize">{selectedNode.category || 'Financial'}</span>
                  </div>
                  <div className="p-2 rounded-lg bg-slate-950/70 border border-slate-800">
                    <span className="text-[10px] font-mono text-slate-500 uppercase block">Accounting Scope</span>
                    <span className="font-semibold text-slate-200">{selectedNode.basis || 'GAAP'} &bull; {selectedNode.scope || 'Consol.'}</span>
                  </div>
                </div>

                {/* Ground-Truth Verbatim Excerpt */}
                <div>
                  <label className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-400 block mb-1">
                    Verbatim Grounding Excerpt
                  </label>
                  <div className="p-3 rounded-lg bg-slate-950 border border-slate-800/80 text-xs font-mono text-slate-300 leading-relaxed">
                    "{selectedNode.snippet || selectedNode.value}"
                  </div>
                </div>

                {/* Source Document Card */}
                <div className="p-3 rounded-lg bg-slate-950/50 border border-slate-800 flex items-center justify-between text-xs">
                  <div>
                    <span className="text-[10px] text-slate-500 font-mono block">Source Document</span>
                    <span className="font-semibold text-slate-200">{selectedNode.document_name}</span>
                  </div>
                  <span className="px-2 py-0.5 rounded bg-cyan-950 text-cyan-300 font-mono font-bold text-[10px]">
                    Page {selectedNode.page_number}
                  </span>
                </div>

                {/* Relationships Involving this Fact */}
                <div>
                  <label className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-400 block mb-1.5">
                    Connected Relationships
                  </label>
                  <div className="space-y-1.5">
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
                          className="p-2 rounded-lg bg-slate-950 border border-slate-800 hover:border-slate-700 cursor-pointer transition-colors"
                          onClick={() => setSelectedEdge(rel)}
                        >
                          <div className="flex items-center justify-between text-xs mb-1">
                            <span
                              className={`font-bold font-mono text-[10px] uppercase ${
                                rel.type === 'CONTRADICTS'
                                  ? 'text-rose-400'
                                  : rel.type === 'SUPERSEDES'
                                  ? 'text-amber-400'
                                  : 'text-emerald-400'
                              }`}
                            >
                              {rel.type}
                            </span>
                            <span className="text-[10px] font-mono text-slate-500">
                              {Math.round((rel.confidence || 0.9) * 100)}% conf
                            </span>
                          </div>
                          <p className="text-[11px] text-slate-300 line-clamp-2 m-0">
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
                      <div className="text-xs text-slate-500 italic p-2 rounded bg-slate-950/40 border border-dashed border-slate-800">
                        No cross-document conflicts or supersessions detected for this single fact.
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* INSPECTOR VIEW 2: RELATIONSHIP EDGE */}
            {selectedEdge && (
              <div className="space-y-4">
                <div>
                  <div className="flex items-center justify-between">
                    <span
                      className={`px-2.5 py-1 rounded-full text-xs font-bold font-mono uppercase ${
                        selectedEdge.type === 'CONTRADICTS'
                          ? 'bg-rose-950/80 text-rose-300 border border-rose-800'
                          : selectedEdge.type === 'SUPERSEDES'
                          ? 'bg-amber-950/80 text-amber-300 border border-amber-800'
                          : 'bg-emerald-950/80 text-emerald-300 border border-emerald-800'
                      }`}
                    >
                      {selectedEdge.type}
                    </span>
                    <span className="text-xs font-mono font-bold text-slate-300">
                      {Math.round((selectedEdge.confidence || 0.9) * 100)}% Confidence
                    </span>
                  </div>
                </div>

                {/* Primary Action Button: View Full Reasoning Trace */}
                <button
                  type="button"
                  className="w-full btn btn-primary btn-sm flex items-center justify-center gap-2 py-2 text-xs font-semibold shadow-md"
                  onClick={() => setActiveReasoningRel({ id: selectedEdge.rel_id || selectedEdge.id })}
                >
                  <IconSparkles className="w-4 h-4 text-amber-300" />
                  <span>View Full Reasoning Trace & Matrix</span>
                </button>

                {/* Explanation Rationale */}
                <div>
                  <label className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-400 block mb-1">
                    LLM Rationale & Conflict Rationale
                  </label>
                  <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-200 leading-relaxed">
                    {selectedEdge.explanation || 'Cross-document reasoning engine identified alignment discrepancy.'}
                  </div>
                </div>

                {/* Fact A vs Fact B Comparison Cards */}
                <div className="space-y-2">
                  <div className="p-3 rounded-lg bg-slate-950 border border-slate-800">
                    <span className="text-[10px] font-mono text-indigo-400 font-bold uppercase block">
                      Fact Claim A
                    </span>
                    <div className="text-xs font-semibold text-white mt-1">
                      {selectedEdge.fact_a_predicate || 'Attribute'}:{' '}
                      <span className="text-emerald-400">{selectedEdge.fact_a_value}</span>
                    </div>
                    <div className="text-[10px] text-slate-400 font-mono mt-1">
                      Doc: {selectedEdge.fact_a_doc || 'Source A'}
                    </div>
                  </div>

                  <div className="p-3 rounded-lg bg-slate-950 border border-slate-800">
                    <span className="text-[10px] font-mono text-purple-400 font-bold uppercase block">
                      Fact Claim B
                    </span>
                    <div className="text-xs font-semibold text-white mt-1">
                      {selectedEdge.fact_b_predicate || 'Attribute'}:{' '}
                      <span className="text-rose-400">{selectedEdge.fact_b_value}</span>
                    </div>
                    <div className="text-[10px] text-slate-400 font-mono mt-1">
                      Doc: {selectedEdge.fact_b_doc || 'Source B'}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* INSPECTOR VIEW 3: ENTITY HUB NODE */}
            {selectedNode && selectedNode.type === 'entity' && (
              <div className="space-y-4">
                <div>
                  <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-indigo-400">
                    Entity Hub
                  </span>
                  <h3 className="text-xl font-bold text-white mt-0.5">{selectedNode.label}</h3>
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
                    <span className="text-[10px] text-slate-500 font-mono block">Grounded Claims</span>
                    <span className="text-base font-bold text-white">{selectedNode.fact_count}</span>
                  </div>
                  <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
                    <span className="text-[10px] text-slate-500 font-mono block">Contradictions</span>
                    <span className="text-base font-bold text-rose-400">{selectedNode.contradiction_count}</span>
                  </div>
                </div>

                <div>
                  <label className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-400 block mb-1.5">
                    Claims For This Entity
                  </label>
                  <div className="space-y-1.5 max-h-80 overflow-y-auto">
                    {graphData.nodes
                      .filter((n) => n.type === 'fact' && n.entity_name === selectedNode.label)
                      .map((f) => (
                        <div
                          key={f.id}
                          className="p-2 rounded-lg bg-slate-950 border border-slate-800 hover:border-indigo-500/60 cursor-pointer transition-colors"
                          onClick={() => setSelectedNode(f)}
                        >
                          <div className="text-xs font-semibold text-white">
                            {f.predicate}: <span className="text-emerald-400">{f.value}</span>
                          </div>
                          <div className="text-[10px] text-slate-400 font-mono mt-0.5 flex items-center justify-between">
                            <span>{f.document_name}</span>
                            <span>p. {f.page_number}</span>
                          </div>
                        </div>
                      ))}
                  </div>
                </div>
              </div>
            )}

            {/* INSPECTOR VIEW 4: DOCUMENT NODE */}
            {selectedNode && selectedNode.type === 'document' && (
              <div className="space-y-4">
                <div>
                  <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-cyan-400">
                    Source Document
                  </span>
                  <h3 className="text-base font-bold text-white mt-0.5">{selectedNode.label}</h3>
                </div>

                <Link
                  to={`/viewer/${selectedNode.document_id}`}
                  className="w-full btn btn-primary btn-sm flex items-center justify-center gap-2 py-2 text-xs font-semibold shadow-md"
                >
                  <IconEye className="w-4 h-4" />
                  <span>Open Entire PDF in Viewer</span>
                </Link>

                <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-2 text-xs">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Total Pages:</span>
                    <span className="text-white font-mono font-bold">{selectedNode.page_count}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Extracted Claims in Graph:</span>
                    <span className="text-cyan-400 font-mono font-bold">{selectedNode.facts_count}</span>
                  </div>
                  {selectedNode.upload_date && (
                    <div className="flex justify-between">
                      <span className="text-slate-500">Ingestion Date:</span>
                      <span className="text-slate-300 font-mono text-[10px]">
                        {new Date(selectedNode.upload_date).toLocaleDateString()}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* DEFAULT EMPTY STATE FOR INSPECTOR */}
            {!selectedNode && !selectedEdge && (
              <div className="text-center py-16 px-4 text-slate-500 space-y-3">
                <IconCompass className="w-10 h-10 text-slate-600 mx-auto" />
                <h4 className="text-xs font-bold text-slate-300">Select any Node or Link</h4>
                <p className="text-xs text-slate-500 leading-relaxed">
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
